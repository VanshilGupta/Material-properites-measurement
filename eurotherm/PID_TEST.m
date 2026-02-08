clear all
instrreset;
%addpath('eurotherm');
pid = tempobj(5);
tempobjconnect(pid);
%tempobjcomm('write', pid, 1, 273, 0);
%tempobjstart(pid);
% try
%     tempobjcomm('readfullres', pid, 1, 2, 1);
% catch ME
%     warning('Write command failed: %s', ME.message);
% end
read = tempobjcomm('readfullres', pid, 1, 2, 1);
disp(read);
delete(pid);
%delete('eurotherm');

% delete(instrfindall);
% 
% pid = tempobj(5); % COM5
% pid.serialObj.BaudRate = 9600;
% pid.serialObj.DataBits = 8;
% pid.serialObj.Parity   = 'even'; % or 'none' if your Eurotherm is set that way
% pid.serialObj.StopBits = 1;
% pid.serialObj.Timeout  = 2;
% 
% tempobjconnect(pid);
% 
% read = tempobjcomm('readfullres', pid, 1, 1, 2);
% disp(read);

% delete(instrfindall);  % clean up old handles
% 
% % Create Eurotherm object using the MDD file, COM5, with LegacyMode=false
% pid = icdevice('eurotherm.mdd', 'COM5', 'LegacyMode', false);
% 
% tempobjconnect(pid);
% 
% try
%     % Example read (address 1, parameter 1, length 2)
%     read = tempobjcomm('readfullres', pid, 1, 1, 2);
%     disp(read);
% catch ME
%     warning("Read failed: %s", ME.message);
% end
% 
% disconnect(pid);
% delete(pid);
