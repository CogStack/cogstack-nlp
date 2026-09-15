ver=$1
echo "Running for version: $ver"
python --version
python -m pip show medcat | grep "Version"


for fn in `ls scripts/speed/*_$ver.sh`;
do
    echo "__________________________"
    echo "Running script:"
    echo $fn
    bash $fn
done
