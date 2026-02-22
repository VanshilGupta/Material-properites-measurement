% clc; close all; clear all
global Eurotherm
% Generate the serial object 
Eurotherm = tempobj(3); 
% Connect to the object: 
tempobjconnect(Eurotherm) 

clear x; 
x = tic;
start_temp = 25.000;
end_temp = 30.000;
count = 1; step_temp = 1.000;
meas_temp = [(start_temp+step_temp):step_temp:end_temp]; % (end_temp-step_temp):-step_temp:start_temp]; 
hold_time = 1; % in minutes

for i=1:8
temp = tempobjcomm('readfullres', Eurotherm, 1, 1, 2)
pause(2)

end

tempobjcomm('writefullres', Eurotherm, 1, 2, 20); % Target setpoint
disp('Target setpoint...done')

% tempobjcomm('writefullres', Eurotherm, 1,161,5); % Ramp rate
% tempobjcomm('writefullres', Eurotherm, 1,23,2); % Program Status

% tempobjcomm('writefullres', Eurotherm, 1,30, 25); %Output high = 10%
% tempobjcomm('writefullres', Eurotherm, 1,31, 0); %Output low = 50%
% Output_high = tempobjcomm('readfullres', Eurotherm, 1,30, 1) %Output high
% Output_low = tempobjcomm('readfullres', Eurotherm, 1,31, 1) %Output low
% 

% tempobjwriteoutputpower(Eurotherm, 1);
tempobjcomm('write', Eurotherm, 1, 273,0); % Select auto mode

% Status is 1 if the controller is running automatically
% (temperature is being regulated), or 0 if in manual mode.
% status = tempobjstatus(Eurotherm)
% tempobjstart(Eurotherm)  % auto mode on
status = tempobjstatus(Eurotherm) % 1 means auto mode
% tempobjwriteoutputpower(Eurotherm, 0)

outputPower = tempobjcomm('readfullres', Eurotherm, 1, 3, 1)
fclose(Eurotherm);
delete(Eurotherm);
return;


%%

tempobjcomm('writefullres', Eurotherm, 1, 2, 450); % Target setpoint

curr_temp = zeros(10000,2); curr_time = zeros(1,10000);
i = 1; outputPower = zeros(1,10000);
clear x; 
x = tic;
meas_temp = 200:50:450;
hold_time = 20;
k = 1;

% get_Temp()
% while count<=((length(meas_temp))+1)
while 1
%   
%     if (curr_time(i) > (hold_time*60))
%         break
%     end
   
curr_time(i) = toc(x)/60;

temp = tempobjcomm('readfullres', Eurotherm, 1, 1, 2);
curr_temp(i,1) = temp(1); % Read Process Variable
curr_temp(i,2) = temp(2); % Read Set temp

outputPower(i) = tempobjcomm('readfullres', Eurotherm, 1, 3, 1);

disp([i curr_time(i) temp outputPower(i)])  

% tempobjcomm('readfullres', Eurotherm, 1, 58, 2)

% y1 = mod(floor(curr_time(i)), hold_time*60);
% y2 = -1;
% try y2 = mod(floor(curr_time(i-1)), hold_time*60);
% catch
% end
% 
% if ( (floor(curr_time(i))>0) && (y1==0) && (y1~=y2) )
%     try tempobjcomm('writefullres', Eurotherm, 1, 2, meas_temp(count))
%     end % 
%     disp('Set working sp...done')
%     count = count+1
% end

% TCtemp = query(KE2700_DMM,'READ?');
% str = ['[' TCtemp ']'];
% TC = eval(str); 
% sample_temp(i) = TC(1);
% 

% subplot(211)
plot(curr_time(i), curr_temp(i,1), 'r-o');
hold on
plot(curr_time(i), curr_temp(i,2), 'b-o');
% plot(curr_time(i), sample_temp(i), 'g-o');


if i < 2
    xlabel('\bfTime (min)');
    ylabel('\bfHeater Temp (degC)')
%     legend({'Heater Temp', 'Set Temp'}, 'Location', 'southeast');
    grid on;
end
    
% subplot(212)
% plot(curr_time(i), outputPower(i), 'b-o');
% hold on
% if i < 2
%     xlabel('\bfTime (min)');
%     ylabel('\bfOutput Power (%)');
%     grid on;
% end

% if curr_time(i) > ramp_times(k)
%     tempobjcomm('writefullres', Eurotherm, 1, 2, meas_temp(k)); % Target setpoint
%     k = k+1;
% end


pause(5)

i = i+1;
end

%%
% tempobjstop(Eurotherm) ;
fclose(Eurotherm);
delete(Eurotherm);

