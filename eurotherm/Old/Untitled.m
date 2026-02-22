% clc; close all; %clear all

% Generate the serial object 
serialObject = tempobj(3); 
% Connect to the object: 
tempobjconnect(serialObject) 

clear x; 
x = tic;
start_temp = 25.000;
end_temp = 30.000;
count = 1; step_temp = 1.000;
meas_temp = [(start_temp+step_temp):step_temp:end_temp]; % (end_temp-step_temp):-step_temp:start_temp]; 
hold_time = 20; % in minutes

temp = [];
    for k=1:5
        try
            temp = tempobjcomm('readfullres', serialObject, 1, 1, 2);
            disp(toc(x), temp)
            break
        catch
            disp(['No response from the PID Controller.... retrying..', num2str(k)])
            pause(5)
            continue
        end
    end
    
if isempty(temp)
    disp('NO RESPONSE FROM EUROTHERM CONTROLLER... TIME OUT ERROR')
    disp('Shutting down the program....')
%         set(handles.meas_start_bttn, 'Value', 1)
    fclose(serialObject);
    delete(serialObject);

    return 
end
    

% tempobjcomm('writefullres', serialObject, 1, 2, 350); % Target setpoint
% disp('Target setpoint...done')


% tempobjcomm('writefullres', serialObject, 1,161,5); % Ramp rate
% tempobjwriteoutputpower(serialObject, 1);
% tempobjcomm('write', serialObject, 1, 273, 1); % Se7lect manual mode

% Status is 1 if the controller is running automatically
% (temperature is being regulated), or 0 if in manual mode.
% status = tempobjstatus(serialObject)
tempobjstart(serialObject)  % auto mode on
status = tempobjstatus(serialObject) % 1 means auto mode
% tempobjwriteoutputpower(serialObject, 0)

outputPower = tempobjcomm('readfullres', serialObject, 1, 3, 1)

while 1
    pause(15)
    if (toc(x) > (hold_time*60))
        break
    end
    
    temp = [];
    for k=1:5
        try
            temp = tempobjcomm('readfullres', serialObject, 1, 1, 2);
            disp(toc(x), temp)
            break
        catch
            disp(['No response from the PID Controller.... retrying', num2str(k)])
            pause(5)
            continue
        end
    end
    
    if isempty(temp)
        disp('NO RESPONSE FROM EUROTHERM CONTROLLER... TIME OUT ERROR')
        disp('Shutting down the program....')
%         set(handles.meas_start_bttn, 'Value', 1)
        fclose(serialObject);
        delete(serialObject);

        return 
    end


end

fclose(serialObject);
delete(serialObject);
return;
 






curr_temp = zeros(10000,2); curr_time = zeros(1,10000);
i = 1; outputPower = zeros(1,10000);

% while count<=((length(meas_temp))+1)
while 1
  
    if (curr_time(i) > (hold_time*60))
        break
    end
   
curr_time(i) = toc(x);

temp = tempobjcomm('readfullres', serialObject, 1, 1, 2);
curr_temp(i,1) = temp(1); % Read Process Variable
curr_temp(i,2) = temp(2); % Read Set temp

outputPower(i) = tempobjcomm('readfullres', serialObject, 1, 3, 1);

disp([i curr_time(i) temp outputPower(i)])

% y1 = mod(floor(curr_time(i)), hold_time*60);
% y2 = -1;
% try y2 = mod(floor(curr_time(i-1)), hold_time*60);
% catch
% end
% 
% if ( (floor(curr_time(i))>0) && (y1==0) && (y1~=y2) )
%     try tempobjcomm('writefullres', serialObject, 1, 2, meas_temp(count))
%     end % 
%     disp('Set working sp...done')
%     count = count+1
% end

subplot(211)
plot(curr_time(i), curr_temp(i,1), 'r-o');
hold on
plot(curr_time(i), curr_temp(i,2), 'b-o');

subplot(212)
plot(curr_time(i), outputPower(i), 'b-o');
hold on
pause(4)

i = i+1;
end

tempobjstop(serialObject) ;
fclose(serialObject);
delete(serialObject);

