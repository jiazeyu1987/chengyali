# Verification Report

Status: completed

## Verified Artifact
- Executable: `E:\ProjectPackage\chenyali\dist\贷款利息自动计提工具.exe`
- Size: `19213505` bytes
- SHA256: `2b710f3e662b17b95b50b8369cd6960f14e1468c026ed897cd9ffefa6d3dafb2`

## Test Results
- Packaging and desktop action regression tests: PASS, 18 passed.
- Build script: PASS, PyInstaller onefile/windowed executable generated.
- Isolated executable runtime test: PASS.

## Runtime Verification
- Ran from temp copy: PASS.
- Listened only on `127.0.0.1:8000`: PASS.
- Template download: PASS.
- Valid Excel calculate path: PASS.
- Export workbook path: PASS.
- Export workbook sheets: `计提结果`, `分段明细`, `公司汇总`, `资本化汇总`, `校验结果`, `计算参数`.
- Export workbook formula count: `0`.
- Embedded exit route stopped executable: PASS.
- Port released after exit: PASS.

## Cleanup Result
- Removed `.artifacts/loan-interest-accrual-exe-v1/pyinstaller-build`.
- Removed `.artifacts/loan-interest-accrual-exe-v1/pyinstaller-spec`.
- Kept `.artifacts/loan-interest-accrual-exe-v1/release/exe-runtime-verification.json`.
- Kept `dist/贷款利息自动计提工具.exe`.
