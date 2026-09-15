echo "*****************"
echo "running v1 stuff"
echo "*****************"

source .venv_v1/bin/activate

bash scripts/speed/run_all_speed_scripts_for_version.sh v1

echo "*****************"
echo "running v2 stuff"
echo "*****************"

source ../.venv312/bin/activate

bash scripts/speed/run_all_speed_scripts_for_version.sh v2
