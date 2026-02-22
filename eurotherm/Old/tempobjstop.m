function tempobjstop(serialObject)
% TEMPOBJSTOP stops temperature control of Eurotherm controllers
% tempobjstop(serialObject) stops temperature control of Eurotherm temperature
% controllers, given a valid serial object - sets it to manual mode and 0%
% output power.

% e.g. tempobjstop(tempobj(7)) stops temperature control of the Eurotherm
% controller attached to COM7.


% check the number of arguments
error(nargchk(1, 1, nargin))

% sets 273 (auto/manual address) to 1 (manual)
tempobjcomm('write', serialObject, 1, 273, 1);

% sets the output power to 0% - this is an invalid command if the
% temperature controller is in automatic mode
tempobjcomm('write', serialObject, 1, 3, 0);