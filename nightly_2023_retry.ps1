# Nocny retry segmentów 2023 (GER40/US100, limit 6000s) + rebuild + push.
# Uruchamiany jednorazowo przez Task Scheduler. Wymaga uruchomionego cTradera
# z pluginem G2BacktestServer na 127.0.0.1:9877 (inaczej segmenty znów => x).
Set-Location "Y:\15_AI\02_TRADING\sezonowosc_backtest"
$env:PYTHONUTF8 = "1"
$log = "nightly_retry.log"
"=== START $(Get-Date -Format s) ===" | Out-File $log -Encoding utf8
python monthly_bt.py            2>&1 | Out-File $log -Append -Encoding utf8
python seasonality_corr.py      2>&1 | Out-File $log -Append -Encoding utf8
python ftmo_swing_sim.py        2>&1 | Out-File $log -Append -Encoding utf8
python build_report.py          2>&1 | Out-File $log -Append -Encoding utf8
git add -A
git -c user.email="sstadniczenko@cnc71.com" -c user.name="sstadniczenko-collab" commit -m "nightly: retry 2023 GER40/US100 + rebuild (auto)" 2>&1 | Out-File $log -Append -Encoding utf8
git push origin main            2>&1 | Out-File $log -Append -Encoding utf8
"=== KONIEC $(Get-Date -Format s) ===" | Out-File $log -Append -Encoding utf8
