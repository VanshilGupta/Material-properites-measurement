B = find(curr_time==0)
curr_temp(B,:) = []
curr_time(B) = []


%%
figure();
plot(curr_time, curr_temp(:,2), 'r-', 'linewidth', 2)
hold on
plot(curr_time, curr_temp(:,1), 'b-o')
ylabel('\bfTemperature (^oC)', 'fontsize', 12)
xlabel('\bfTime in minutes', 'fontsize', 12)
grid on
legend({'Set Temp.', 'Process Temp.'}, 'fontsize', 12)
title('Hall-Setup Heater Temp Profile in AIR', 'fontsize', 15)


%%

disp('Gain scheduler setpoint')
tempobjcomm('read', Eurotherm, 1, 153, 1)

disp('Current PID set')
tempobjcomm('read', Eurotherm, 1, 72, 1)
% 0: Set 1
% 1: Set 2

disp('Proportional band PID1')
tempobjcomm('read', Eurotherm, 1, 6, 1)

disp('Integral time PID1')
tempobjcomm('read', Eurotherm, 1, 8, 1)

disp('Derivative time PID1')
tempobjcomm('read', Eurotherm, 1, 9, 1)

disp('Manual reset PID1')
tempobjcomm('read', Eurotherm, 1, 28, 1)


disp('Cutback high PID1. 0: Auto')
tempobjcomm('read', Eurotherm, 1, 18, 1)

disp('Cutback low PID1. 0: Auto')
tempobjcomm('read', Eurotherm, 1, 17, 1)


%%%%%%
disp('Proportional band PID1')
tempobjcomm('read', Eurotherm, 1, 48, 1)

disp('Integral time PID1')
tempobjcomm('read', Eurotherm, 1, 49, 1)

disp('Derivative time PID1')
tempobjcomm('read', Eurotherm, 1, 51, 1)

disp('Manual reset PID1')
tempobjcomm('read', Eurotherm, 1, 50, 1)


disp('Cutback high PID1. 0: Auto')
tempobjcomm('read', Eurotherm, 1, 118, 1)

disp('Cutback low PID1. 0: Auto')
tempobjcomm('read', Eurotherm, 1, 117, 1)




