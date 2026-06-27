import gi
gi.require_version("Gst", "1.0")
from gi.repository import Gst, GLib
import struct
import sys
import os

def generate_waveform_data(filepath: str, num_points: int = 150) -> list[float]:
    """
    Decodes an audio file to raw mono S16LE samples using GStreamer appsink,
    and downsamples it to a list of floats (0.0 to 1.0) of size num_points.
    """
    if not os.path.exists(filepath):
        return []

    try:
        if not Gst.is_initialized():
            Gst.init(None)
            
        pipeline = Gst.Pipeline.new("waveform-pipeline")
        src = Gst.ElementFactory.make("filesrc", "src")
        src.set_property("location", filepath)
        
        dec = Gst.ElementFactory.make("decodebin", "dec")
        conv = Gst.ElementFactory.make("audioconvert", "conv")
        
        filt = Gst.ElementFactory.make("capsfilter", "filter")
        caps = Gst.Caps.from_string("audio/x-raw,format=S16LE,channels=1")
        filt.set_property("caps", caps)
        
        sink = Gst.ElementFactory.make("appsink", "sink")
        sink.set_property("emit-signals", True)
        sink.set_property("max-buffers", 1)
        sink.set_property("drop", False)
        sink.set_property("sync", False)
        
        if not all([src, dec, conv, filt, sink]):
            return []
            
        pipeline.add(src)
        pipeline.add(dec)
        pipeline.add(conv)
        pipeline.add(filt)
        pipeline.add(sink)
        
        src.link(dec)
        conv.link(filt)
        filt.link(sink)
        
        def on_pad_added(element, pad):
            sink_pad = conv.get_static_pad("sink")
            if not sink_pad.is_linked():
                pad.link(sink_pad)
                
        dec.connect("pad-added", on_pad_added)
        
        samples = []
        
        def on_new_sample(appsink):
            sample = appsink.emit("pull-sample")
            if not sample:
                return Gst.FlowReturn.OK
            buf = sample.get_buffer()
            success, map_info = buf.map(Gst.MapFlags.READ)
            if success:
                try:
                    samples.append(map_info.data)
                finally:
                    buf.unmap(map_info)
            return Gst.FlowReturn.OK
            
        sink.connect("new-sample", on_new_sample)
        
        pipeline.set_state(Gst.State.PLAYING)
        
        bus = pipeline.get_bus()
        while True:
            # Usar un timeout de 2 segundos para evitar bloqueos si faltan códecs en Ubuntu/WSL
            msg = bus.timed_pop_filtered(2 * Gst.SECOND, Gst.MessageType.EOS | Gst.MessageType.ERROR)
            if msg:
                if msg.type == Gst.MessageType.ERROR:
                    err, debug = msg.parse_error()
                    print(f"GStreamer Waveform Error for {filepath}: {err} - {debug}", file=sys.stderr)
                break
            else:
                # Se alcanzó el timeout (msg es None)
                print(f"GStreamer Waveform timeout (posible falta de códecs) para {filepath}", file=sys.stderr)
                break
                
        pipeline.set_state(Gst.State.NULL)
        
        if not samples:
            return []
            
        all_data = b"".join(samples)
        if not all_data:
            return []
            
        num_samples = len(all_data) // 2
        if num_samples == 0:
            return []
            
        chunk_size = max(1, num_samples // num_points)
        waveform = []
        
        mv = memoryview(all_data)
        for i in range(num_points):
            start_idx = i * chunk_size
            end_idx = min(num_samples, (i + 1) * chunk_size)
            if start_idx >= num_samples:
                waveform.append(0.0)
                continue
                
            chunk_bytes = mv[start_idx*2 : end_idx*2]
            if not chunk_bytes:
                waveform.append(0.0)
                continue
                
            fmt = f"<{len(chunk_bytes)//2}h"
            try:
                chunk_vals = struct.unpack(fmt, chunk_bytes)
                peak = max(abs(val) for val in chunk_vals)
                waveform.append(float(peak))
            except Exception:
                waveform.append(0.0)
                
        max_val = max(waveform) if waveform else 0
        if max_val > 0:
            waveform = [val / max_val for val in waveform]
        else:
            waveform = [0.0] * num_points
            
        return waveform
    except Exception as e:
        print(f"Exception generating waveform for {filepath}: {e}", file=sys.stderr)
        return []
