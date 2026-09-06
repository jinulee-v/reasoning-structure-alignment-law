/* ---------------  Facts --------------- */

% itinerary facts
origin(tokyo).
destination(portland).
class(business).
ticket_price(543).

% every bag is described as  bag(Id, Length, Width, Height, Weight).
bag(1, 19, 14,  7, 12).
bag(2, 38, 15, 10, 51).
bag(3, 34, 18, 12, 59).
bag(4, 44, 30, 19, 94).
bag(5, 35, 18, 12, 91).
bag(6, 49, 26, 22, 97).
bag(7, 34, 18, 13, 52).
bag(8, 49, 27, 26, 58).

/* ---------------  Helper predicates --------------- */

% sum of outside dimensions
size_sum(L,W,H,S) :- S is L+W+H.

% A bag qualifies as the single carry-on item if every dimension is within the carry-on
% limits: 22 x 14 x 9 in.
carry_on(Id) :-
    bag(Id,L,W,H,_),
    L =< 22 , W =< 14 , H =< 9.

% which bags are checked (all bags that are not the carry-on)
checked_bag_ids(CheckedIds) :-
    findall(Id, (bag(Id,_,_,_,_), \+ carry_on(Id)), CheckedIds0),
    sort(CheckedIds0, CheckedIds).           % keep ascending order (1,2,3 ...)

% the N-th checked bag gets its 0-based index (Idx 0 is 1st checked, Idx 1 is 2nd ...)
checked_bag_index(BagId,Idx) :-
    checked_bag_ids(Ids),
    nth0(Idx,Ids,BagId).

/* ---------------  Base checked-bag fees (Business, Tokyo<->USA) --------------- */

% first two checked bags are free, every further bag costs 200 USD
base_checked_fee(Idx,0)  :- Idx =< 1.           % Idx 0 or 1  -> 1st / 2nd checked
base_checked_fee(Idx,200) :- Idx  > 1.          % 3rd + bags

/* ---------------  Oversize fee (Tokyo<->USA) --------------- */

oversize_fee(BagId,Fee) :-
    bag(BagId,L,W,H,_),
    size_sum(L,W,H,S),
    (   S =< 62                     -> Fee = 0
    ;   S =< 65                     -> Fee = 30
    ;   S =< 115                    -> Fee = 200
    ;   S  > 115                    -> Fee = 99999      % not relevant here
    ).

/* ---------------  Overweight fee (Tokyo<->USA) --------------- */

% Allowed weight limit: 70 lb for the first two (free) checked bags, otherwise 50 lb
weight_limit(Idx,70) :- Idx =< 1.
weight_limit(Idx,50) :- Idx  > 1.

overweight_fee(BagId,Idx,Fee) :-
    bag(BagId,_,_,_,W),
    weight_limit(Idx,Lim),
    (   W =< Lim                    -> Fee = 0
    ;   W  >  70                    -> Fee = 450   % 70-100 lb band
    ;   W  >  53                    -> Fee = 100   % 53-70
    ;   W  >  50                    -> Fee = 30    % 50-53
    ).

/* ---------------  Final bag cost --------------- */

bag_cost(BagId,Cost) :-
    checked_bag_index(BagId,Idx),
    base_checked_fee(Idx,Base),
    oversize_fee(BagId,OS),
    overweight_fee(BagId,Idx,OW),
    MaxExtra is max(OS,OW),           % only the higher of the two applies
    Cost    is Base + MaxExtra.

total_baggage_cost(Total) :-
    checked_bag_ids(Ids),
    findall(C, (member(Id,Ids), bag_cost(Id,C)), Costs),
    sum_list(Costs,Total).

/* ---------------  Grand total (ticket + bags) --------------- */

total_cost(Total) :-
    ticket_price(Fare),
    total_baggage_cost(Bags),
    Total is Fare + Bags.

/* ---------------  Query --------------- */

:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.