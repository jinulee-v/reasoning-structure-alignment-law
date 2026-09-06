/* ----------  Statutory rules needed for this case ---------- */

% the passenger and itinerary
class(premium_economy).
region(to_from_japan).          % Houston - Nagoya
flight_fare(343).

% bag facts:  bag(Id, Length, Width, Height, Weight).
bag(1, 21,12, 8, 11).
bag(2, 38,13,14, 90).
bag(3, 38,14,11, 59).
bag(4, 43,22,21, 52).
bag(5, 35,23,13, 70).
bag(6, 45,20,22, 93).
bag(7, 33,19,13, 56).
bag(8, 37,13,13, 53).

/* ----------  Carry-on test ---------- */
carryon_size_limit(22,14,9).

is_carryon(BagID) :-
    bag(BagID,L,W,H,_),
    carryon_size_limit(ML,MW,MH),
    L =< ML, W =< MW, H =< MH.

checked_bag(BagID) :- bag(BagID,_,_,_,_), \+ is_carryon(BagID).

/* ----------  Base checked-bag fee (Premium Economy, Japan) ---------- */
% 1st & 2nd checked bags are free, 3rd = $200, 4th+ = $200
base_fee(Index, 0)  :- Index =< 2.        % free allowance
base_fee(Index,200) :- Index >= 3.

/* ----------  Oversize / overweight extra fees ---------- */
dimsum(L,W,H,S) :- S is L+W+H.

oversize_fee(L,W,H, 0)  :- dimsum(L,W,H,S), S =< 62.
oversize_fee(L,W,H,30)  :- dimsum(L,W,H,S), S > 62, S =< 65.
oversize_fee(L,W,H,200) :- dimsum(L,W,H,S), S > 65, S =< 115.

overweight_fee(Weight, 0)   :- Weight =< 50.
overweight_fee(Weight, 30)  :- Weight  > 50, Weight =< 53.
overweight_fee(Weight,100)  :- Weight  > 53, Weight =< 70.
overweight_fee(Weight,450)  :- Weight  > 70, Weight =< 100.

/* choose the higher of the two extras */
extra_fee(L,W,H,Weight,F) :-
    oversize_fee(L,W,H,OS), overweight_fee(Weight,OW),
    F is max(OS,OW).

/* ----------  Fee for each checked bag ---------- */
bag_fee(BagID,Index,TotalFee) :-
    bag(BagID,L,W,H,Weight),
    base_fee(Index,Base),
    extra_fee(L,W,H,Weight,Extra),
    TotalFee is Base + Extra.

/* ----------  Sum of all checked-bag fees ---------- */
checked_bag_list(List) :- findall(ID, checked_bag(ID), List).

total_bag_fees(Sum) :-
    checked_bag_list(List),
    bag_fees(List,1,Sum).

bag_fees([],_,0).
bag_fees([BagID|Rest],Index,Sum) :-
    bag_fee(BagID,Index,F1),
    NextIndex is Index + 1,
    bag_fees(Rest,NextIndex,RestSum),
    Sum is F1 + RestSum.

/* ----------  Grand total ---------- */
total_cost(Total) :-
    flight_fare(Fare),
    total_bag_fees(BagSum),
    Total is Fare + BagSum.

/* ----------  Query and output ---------- */
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.