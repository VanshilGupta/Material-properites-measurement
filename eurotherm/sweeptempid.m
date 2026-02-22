instrreset;  % Resets and clears all instrument objects (legacy)
clear all;   % Clears all variablesclear all;
%addpath('subfunctions_Hall');
addpath('eurotherm');

n=100; %number of temp readings
p=2; %pause between subsequent readings

times = strings(n,1);
vals = zeros(n,1);


Eurotherm = tempobj(5); %COM5 serial port
tempobjconnect(Eurotherm);

%for Auto or Manual Mode(logic=0 for auto)
tempobjcomm('write', Eurotherm, 1, 273, 0); 
mode = tempobjcomm('read', Eurotherm, 1, 273, 1);
disp(mode)

% set temp to 0 degree
tempobjcomm('write', Eurotherm, 1, 2, 0);
status = tempobjstatus(Eurotherm) % 1 means auto mode
 
% reads both actual temp + set temp
temp = tempobjcomm('readfullres', Eurotherm, 1, 1, 2);
disp(temp)


% set temperature
set_temp= 50;
tempobjcomm('write', Eurotherm, 1, 2, set_temp);

% set rate limit (degress/min)
tempobjcomm('writefullres', Eurotherm, 1, 35, 360);

rateLimit = tempobjcomm('readfullres', Eurotherm, 1, 35, 1);
fprintf('Current rate limit value: %.2f °C\n', rateLimit)


setTemp = tempobjcomm('readfullres', Eurotherm, 1, 2, 1);
fprintf('Current setpoint value: %.2f °C\n', setTemp);
pause(1)

setTemp = tempobjcomm('readfullres', Eurotherm, 1, 1, 2);
disp(['Setpoint temperature is: ', num2str(setTemp)]);


start_time = datestr(now,'dd-mmm-yyyy-HH-MM-SS'); %%% FIXME: add date also

for i = 1:n

    val = tempobjcomm('readfullres', Eurotherm, 1, 1, 1);
    times(i,1)= datestr(now,'HH:MM:SS.FFF');
    vals(i,1)=val;
    pause(p);
end
t= 0:p:(p*(n-1));

figure;
plot(t, vals, '-o', 'LineWidth', 2);
xlabel('Time (s)');
ylabel('Temperature Voltage (V)');
title('Temperature-Time Graph');
grid on;



data = table(times,vals);
filename = "test1_"+set_temp+"C_"+start_time+".xlsx";
writetable(data, filename);

tempobjcomm('write', Eurotherm, 1, 2, 25);
%tempobjcomm('write', Eurotherm, 1, 3, 0);

fclose(Eurotherm);
delete(Eurotherm);
clear Eurotherm;
