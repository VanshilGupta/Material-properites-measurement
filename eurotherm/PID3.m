% clear all
% instrreset;
% pid = tempobj(5);
% tempobjconnect(pid);
% 
% tempobjcomm('write', pid, 1, 273, 0); 
% mode = tempobjcomm('read', pid, 1, 273, 1);
% disp(mode);


clear all
instrreset;

pid = tempobj(5);
tempobjconnect(pid);

% Desired setpoint
settemp = 25.0; 
%settemp_raw = int16(settemp * 10);   % convert to raw register units

% Write to parameter address 2 (SP)
tempobjcomm('write', pid, 1, 2, settemp);

% Read back PV and SP (2 registers starting at 1)
read = tempobjcomm('readfullres', pid, 1, 1, 2);
disp(read);

delete(pid);










































%settemp = 41;
%settemp = 41.0;
%settemp_raw = int16(settemp * 10);   % convert °C to Eurotherm register units

% tempobjcomm('writefullres', pid, 1, 2, 41);
% 
% %tempobjcomm('writefullres', pid, 1, 2, settemp);
% read = tempobjcomm('readfullres', pid, 1, 1, 2);
% disp(read);
delete(pid);
