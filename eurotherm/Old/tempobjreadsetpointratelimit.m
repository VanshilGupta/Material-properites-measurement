function rateLimit = tempobjreadsetpointratelimit(serialObject)
% TEMPOBJREADSETPOINTRATELIMIT Reads set point rate limit for Eurotherms
% rateLimit = tempobjreadsetpointratelimit(serialObject) Reads set point
% rate limite in °C/min from Eurotherm temperature controllers given an
% appropriate serial port object (generated from tempobj).  0 disables the
% rate limit.

% e.g. rateLimit = tempobjreadsetpointlimit(tempobj(7)) - gives set point
% rate limit in °C/min from the device on COM7, usually 0.

% Range:

% serialObject = valid serial port object


% checks the number of arguments
error(nargchk(1, 1, nargin))

% retrieves information
rateLimit = tempobjcomm('readfullres', serialObject, 1, 35, 1);