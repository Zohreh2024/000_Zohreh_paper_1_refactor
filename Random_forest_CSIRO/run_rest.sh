set -e
CONDA='conda run --no-capture-output -p C:\ProgramData\Anaconda3\envs\JinzhuLuto'
echo "=== Step_03 start $(date)"
$CONDA python -u Step_03_build_model.py --jobs 96 > logs/step03.log 2>&1
echo "=== Step_03 done $(date)"
tail -40 logs/step03.log
echo "=== Step_04 start $(date)"
$CONDA python -u Step_04_predict_future.py --jobs 6 --model-jobs 12 > logs/step04.log 2>&1
echo "=== Step_04 done $(date)"
tail -15 logs/step04.log
echo "=== Step_05 start $(date)"
$CONDA python -u Step_05_plots.py > logs/step05.log 2>&1
tail -12 logs/step05.log
echo "=== Step_06 start $(date)"
$CONDA python -u Step_06_write_report.py > logs/step06.log 2>&1
cat logs/step06.log
echo "=== ALL DONE $(date)"
ls -la *.docx plots/
