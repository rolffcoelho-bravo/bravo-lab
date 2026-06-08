setup:
	python -m pip install -r requirements.txt

smoke-test:
	python -c "import sys; sys.path.insert(0, 'src'); from bravo.data import load_market_data; print('BRAVO Lab smoke test passed: imports are working.')"

report:
	python -c "import sys; sys.path.insert(0, 'src'); from bravo.report import generate_baseline_report; print(generate_baseline_report())"

test:
	python -c "print('Tests will be added after the baseline pipeline is stabilized.')"

clean:
	python -c "import shutil, pathlib; [shutil.rmtree(p, ignore_errors=True) for p in pathlib.Path('.').rglob('__pycache__')]; print('Cache folders removed.')"
