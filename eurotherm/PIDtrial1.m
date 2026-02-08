% % Create Modbus RTU connection on COM5
% m = modbus("serialrtu", "COM5", 9600, ...
%            "Parity","none","DataBits",8,"StopBits",1,"Timeout",2);
% 
% % Write SP = 41.0 °C (Eurotherm uses tenths of a degree)
% write(m, "holdingregs", 2, uint16(410), "SlaveID", 1);
% 
% % Read back PV (register 1)
% raw = read(m, "holdingregs", 1, 1, "uint16", "SlaveID", 1);
% pv = double(raw) / 10;
% disp("PV = " + pv + " °C");
% delete(m);
clear all
instrreset
% Create Modbus RTU connection on COM5
m = modbus('serialrtu', 'COM5', 9600, ...
           'Parity','none', 'DataBits',8, 'StopBits',1, 'Timeout',2);

% Write SP = 41.0 °C (Eurotherm stores tenths of degrees, so 410 = 41.0 °C)
write(m, 'holdingregs', 2, uint16(410), 'SlaveID', 1);

% Read PV (parameter 1)
rawPV = read(m, 'holdingregs', 1, 1, 'uint16', 'SlaveID', 1);
pv = double(rawPV)/10;
disp("PV = " + pv + " °C");

% Read SP back (parameter 2)
rawSP = read(m, 'holdingregs', 2, 1, 'uint16', 'SlaveID', 1);
sp = double(rawSP)/10;
disp("SP = " + sp + " °C");
