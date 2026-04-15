cd e:\Suilli10086\suilli_mizi\tools\job_eval
python -m venv .venv
pip install -r requirements.txt
.\.venv\Scripts\Activate.ps1
deactivate


cd e:\Suilli10086\suilli_mizi\backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python run.py
deactivate

#工具包运行
cd tools/job_eval
python run_job_eval_batch.py --dry-run --env .env  
#正式写回
python run_job_eval_batch.py --env .env

#导入结果
cd tools/job_eval
python import_job_eval_jsonl.py --env .env --input job_eval_results_20260414_100000.jsonl

cd e:\Suilli10086\suilli_mizi\frontend
pnpm install
pnpm dev