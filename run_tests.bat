@echo off
REM Batch script to run GlickoTR single match calculations for predefined scenarios

REM Get the directory where the script resides
SET SCRIPT_DIR=%~dp0

REM Ensure python is in PATH or specify full path
SET PYTHON_EXE=python

REM Scenario 1: Baseline Even Match (Completed)
echo Running Scenario 1: Baseline Even Match...
%PYTHON_EXE% "%SCRIPT_DIR%glickoTR_atomic_test.py" --p1_mu 1500.0 --p1_phi 350.0 --p1_sigma 0.06 --p2_mu 1500.0 --p2_phi 350.0 --p2_sigma 0.06 --p1_games 13 --p2_games 8 --status completed > "%SCRIPT_DIR%scenario1_expected.json"
if %errorlevel% neq 0 (
    echo Error running Scenario 1!
    goto end
)

REM Scenario 2: Mismatch Upset (Completed)
echo Running Scenario 2: Mismatch Upset...
%PYTHON_EXE% "%SCRIPT_DIR%glickoTR_atomic_test.py" --p1_mu 1400.0 --p1_phi 150.0 --p1_sigma 0.05 --p2_mu 1700.0 --p2_phi 100.0 --p2_sigma 0.04 --p1_games 13 --p2_games 10 --status completed > "%SCRIPT_DIR%scenario2_expected.json"
if %errorlevel% neq 0 (
    echo Error running Scenario 2!
    goto end
)

REM Scenario 3: Retirement (Higher ranked retires)
echo Running Scenario 3: Retirement (Higher ranked retires, P2 wins)...
%PYTHON_EXE% "%SCRIPT_DIR%glickoTR_atomic_test.py" --p1_mu 1600.0 --p1_phi 80.0 --p1_sigma 0.06 --p2_mu 1500.0 --p2_phi 120.0 --p2_sigma 0.06 --p1_games 7 --p2_games 7 --status retired > "%SCRIPT_DIR%scenario3_expected.json"
if %errorlevel% neq 0 (
    echo Error running Scenario 3!
    goto end
)

REM Scenario 4: High RD Players (Completed)
echo Running Scenario 4: High RD Players...
%PYTHON_EXE% "%SCRIPT_DIR%glickoTR_atomic_test.py" --p1_mu 1550.0 --p1_phi 400.0 --p1_sigma 0.06 --p2_mu 1450.0 --p2_phi 380.0 --p2_sigma 0.06 --p1_games 12 --p2_games 1 --status completed > "%SCRIPT_DIR%scenario4_expected.json"
if %errorlevel% neq 0 (
    echo Error running Scenario 4!
    goto end
)

echo All scenarios processed successfully.
echo Expected results saved to scenarioX_expected.json files.

:end
REM pause 