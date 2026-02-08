function response = isvalidtempobjmaxwords(maxWords)
% ISVALIDTEMPOBJMAXWORDS checks for suitability
% currently only a simple check due to the variety of possible values -
% kept as a subfunction as unlikely to be required by any other function.
% Note that very few Modbus devices will actually be able to read/write
% this many words.

response = isnumeric(maxWords) && isscalar(maxWords) && maxWords >= 1 && maxWords <= 65535;