function out = get_Temp()
global KE2700_DMM

fprintf(KE2700_DMM, 'TRAC:CLEAR');
fprintf(KE2700_DMM, '*RST')

pause(2)

fprintf(KE2700_DMM, 'SYST:TST:TYPE REL'); %RTCL OR REL
% fprintf(KE2700_DMM, 'DISP:ENAB OFF');
fprintf(KE2700_DMM, 'INIT:CONT OFF'); % Disable continuous initiation.
fprintf(KE2700_DMM, 'TRAC:CLE');
fprintf(KE2700_DMM, 'TRAC:CLE:AUTO OFF');
fprintf(KE2700_DMM, 'FORMat:ELEMents READing, TSTamp');

fprintf(KE2700_DMM,'SENS:FUNC "TEMP",(@118)');
fprintf(KE2700_DMM,'UNIT:TEMP C,(@118)');
fprintf(KE2700_DMM,'TEMP:TRAN TC,(@118)');
fprintf(KE2700_DMM,'TEMP:TC:TYPE K,(@118)'); % K Type Thermocouple
fprintf(KE2700_DMM, 'TEMP:TC:RJUN:RSEL INT,(@118)');
fprintf(KE2700_DMM,'TEMP:NPLC 5,(@118)');

fprintf(KE2700_DMM, 'ROUT:SCAN (@118)'); 
fprintf(KE2700_DMM, 'ROUT:SCAN:TSO IMM');
fprintf(KE2700_DMM, 'TRIG:COUN 1');
fprintf(KE2700_DMM, 'SAMP:COUN 1');
fprintf(KE2700_DMM, 'TRIG:SOUR IMM');
fprintf(KE2700_DMM, 'ROUT:SCAN:LSEL INT'); 

TCtemp = query(KE2700_DMM,'READ?');
str = ['[' TCtemp ']'];
TC = eval(str); 

out = TC(1);