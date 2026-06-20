#!/bin/bash
# Obtener el directorio absoluto donde reside este script
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Ejecutar usando el intérprete de python del entorno virtual y configurando PYTHONPATH
PYTHONPATH="$DIR/src" "$DIR/.venv/bin/python" -m soundwave "$@"
