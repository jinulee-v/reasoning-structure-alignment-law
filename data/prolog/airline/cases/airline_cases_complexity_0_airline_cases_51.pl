/*  ----------  STATUTORY RULES (excerpted / simplified for this case)  ---------- */

% route of this itinerary
route(within_us).             % Boston - Miami

% passenger commercial class
class(business).

% complimentary checked-bag allowance for Business Class on a domestic (within U.S.) itinerary
complimentary_bags(2).        % 1st & 2nd checked bags free

/* ----------  BASE CHECKED-BAG FEES  ---------- */

% base fee for bag number N on this itinerary
base_checked_fee(N, Fee) :-
    complimentary_bags(C),
    N =< C, !,                % bags within free allowance cost $0
    Fee = 0.
base_checked_fee(3, 150) :- !.          % 3rd bag
base_checked_fee(N, 200) :- N >= 4.     % 4th bag and any above

/* ----------  SURCHARGE FOR WEIGHT  ---------- */

% overweight_fee(WeightLbs, Fee)
overweight_fee(W, 0)  :- W =< 50, !.                % not overweight
overweight_fee(W, 30) :- W =< 53, W  > 50, !.       % 50-53 lbs
overweight_fee(W, 100) :- W =< 70, W  > 53, !.      % 53-70 lbs
overweight_fee(W, 200) :- W =< 100, W > 70, !.      % 70-100 lbs (within U.S.)
overweight_fee(_, 200).                             % heavier not accepted - use 200 cap for logic here

/* ----------  SURCHARGE FOR SIZE  ---------- */

% oversize_fee(TotalLinearInches, Fee)
oversize_fee(S, 0)  :- S =< 62, !.                  % within standard size
oversize_fee(S, 30) :- S =< 65, S  > 62, !.         % 62-65 in
oversize_fee(S, 200) :- S =< 115, S > 65, !.        % 65-115 in (within U.S.)
oversize_fee(_, 200).                               % larger not accepted - use 200 cap for logic here

/* ----------  EFFECTIVE SURCHARGE FOR A BAG  ---------- */

effective_surcharge(Weight, SizeSum, Surcharge) :-
    overweight_fee(Weight, OFee),
    oversize_fee(SizeSum,  SFee),
    Surcharge is max(OFee, SFee).

/* ----------  CHECKED-BAG FACTS FOR THIS CASE  ---------- */

% checked_bag(Number, WeightLbs, [L,W,H])
checked_bag(1, 51, [43,30,20]).
checked_bag(2, 97, [40,13,16]).
checked_bag(3, 87, [46,28,23]).
checked_bag(4, 91, [46,23,19]).

/* ----------  TOTAL FOR ALL CHECKED BAGS  ---------- */

bag_cost(BagNum, Cost) :-
    checked_bag(BagNum, Weight, Dims),
    sumlist(Dims, SizeSum),
    base_checked_fee(BagNum, Base),
    effective_surcharge(Weight, SizeSum, Surch),
    Cost is Base + Surch.

total_checked_bags_cost(Total) :-
    findall(C, (checked_bag(N,_,_), bag_cost(N,C)), Costs),
    sumlist(Costs, Total).

/* ----------  TOTAL TRAVEL COST  ---------- */

ticket_price(36).

total_cost(Total) :-
    ticket_price(Tix),
    total_checked_bags_cost(Bags),
    Total is Tix + Bags.

/* ----------  QUERY  ---------- */

:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.