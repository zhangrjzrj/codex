# Legacy Tracy Notes

- Some old `.tracy` captures can be opened by older GUI profilers but fail in `tracy-csvexport.exe`.
- In this case the analyzer marks `analysis_mode=legacy-screenshot`.
- Treat screenshot mode as evidence collection, not as a full machine-readable analysis.
- If later automation is added for GUI navigation, extend the script instead of replacing the CSV path.
