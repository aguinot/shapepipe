# !/bin/bash

# Set path to package module
export PACKAGE_DIR="$HOME/ShapePipe/modules/template_package"

# Run package
python ${PACKAGE_DIR}/package_name/package_name_SMP.py -d ${PACKAGE_DIR}/config -c package_config_smp.cfg
