function tempobjstart(serialObject)
% TEMPOBJSTART starts temperature control of Eurotherm controllers
% tempobjstart(serialObject) starts temperature control of Eurotherm temperature
% controllers, given a valid serial object.

% e.g. tempobjstart(tempobj(7)) starts temperature control of the Eurotherm
% controller attached to COM7.


% check the number of arguments
error(nargchk(1, 1, nargin))

% sets 273 (auto/manual) to 0 (auto)
tempobjcomm('write', serialObject, 1, 273, 0);