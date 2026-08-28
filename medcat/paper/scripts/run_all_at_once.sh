echo "*****************"
echo "Performance"
echo "*****************"

bash scripts/performance/get_performance_all.sh

echo "*****************"
echo "Regression"
echo "*****************"

bash scripts/performance/get_regression_all.sh

echo "*****************"
echo "Speed"
echo "*****************"
    
bash scripts/speed/run_all_speed_scripts.sh

echo "*****************"
echo "Variance"
echo "*****************"

bash scripts/variance/get_variance_with_linker_and_tokenizer_all.sh
