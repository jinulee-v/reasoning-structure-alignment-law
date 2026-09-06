/*************************************************************************
  Statutory rules and facts needed for this single case
*************************************************************************/

% ------------------------------
% Passenger / flight information
% ------------------------------
flight(karen,
       phoenix,                 % origin (U.S.)
       rio_de_janeiro,          % destination (Brazil - South America,
                                %              excluding the special cases)
       basic_economy,           % service class
       563).                    % ticket price in US$

% ---------------------------------
% Checked-bag data supplied in case
% bag(Number, Length, Width, Height, Weight)
% (Carry-on / personal item is free and therefore omitted.)
% ---------------------------------
bag(1,38,18, 9,64).   % luggage box
bag(2,35,15,14,53).   % backpack
bag(3,43,24,20,53).   % backpack
bag(4,36,18,10,52).   % luggage box

/*************************************************************************
  Helper predicates
*************************************************************************/

% Sum of outside linear dimensions of a bag
dim_sum(Id,Sum) :-
    bag(Id,L,W,H,_),
    Sum is L + W + H.

% ----------------------------------------------------
% Overweight fee (depends on weight *only*)
% Route category : S. America <-> U.S. / Canada / ... etc.
% ----------------------------------------------------
overweight_fee(Weight,Fee) :-
         Weight =< 50 -> Fee = 0
 ; 50  < Weight, Weight =< 53 -> Fee = 30
 ; 53  < Weight, Weight =< 70 -> Fee = 100
 ; 70  < Weight, Weight =< 100-> Fee = 200
 ;                                   Fee = 999999.   % "not accepted" zone

% ----------------------------------------------------
% Oversize fee (depends on linear dimensions *only*)
% Route category : South America (except GY/SR) <-> U.S.
% ----------------------------------------------------
oversize_fee(Size,Fee) :-
         Size =< 62  -> Fee = 0
 ; 62  < Size, Size =< 65  -> Fee = 30
 ; 65  < Size, Size =< 115 -> Fee = 150
 ;                                   Fee = 999999.

% ----------------------------------------------------
% Extra fee for a bag: choose the HIGHER of overweight
% and oversize surcharges (rule from statute)
% ----------------------------------------------------
extra_fee(Id,Extra) :-
    bag(Id,_,_,_,W),
    dim_sum(Id,S),
    overweight_fee(W,OW),
    oversize_fee(S,OS),
    Extra is max(OW,OS).

% ----------------------------------------------------
% Basic checked-bag fee by bag sequence number for
% Basic Economy on a U.S. -> South America itinerary
% ----------------------------------------------------
base_fee(1,60).
base_fee(2,100).
base_fee(3,200).
base_fee(N,200) :- N>=4.

% ----------------------------------------------------
% Total for each checked bag = base + extra
% ----------------------------------------------------
bag_total(Id,Total) :-
    base_fee(Id,Base),
    extra_fee(Id,Extra),
    Total is Base + Extra.

% ----------------------------------------------------
% Sum all checked-bag fees
% ----------------------------------------------------
total_bag_fees(Total) :-
    findall(T, (between(1,4,Id), bag_total(Id,T)), List),
    sum_list(List, Total).

/*************************************************************************
  Final cost (ticket + all bag fees)
*************************************************************************/
total_cost(GrandTotal) :-
    flight(karen,_,_,_,Ticket),
    total_bag_fees(BagFees),
    GrandTotal is Ticket + BagFees.

/*************************************************************************
  Query: print the result exactly as required
*************************************************************************/
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.