delete(instrfindall);
m = modbus('serialrtu', "COM5", 9600, ...
           "Parity", "even", "DataBits", 8, "StopBits", 1, "Timeout", 2);

% Read process variable (PV). Commonly at holding register 1 (40001).
raw = read(m, "holdingregs", 1, 1, "uint16");

% Eurotherm usually scales temperature by 10 (e.g., 237 -> 23.7 °C)
temperature = double(raw) / 10;

disp(temperature);