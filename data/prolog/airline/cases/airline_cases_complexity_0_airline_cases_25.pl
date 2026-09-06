/*********************************************************************
   Rules derived from the statutes
*********************************************************************/

% route(+From,+To, -RouteType)
route(roma, 'salt_lake_city', europe_us).    % Rome (Italy, Europe) -> U.S.

% base checked-bag fee for Main Cabin on a Europe<->U.S. itinerary
% bag_index is 1-based among the checked pieces
base_fee(main_cabin, europe_us, 1, 0).
base_fee(main_cabin, europe_us, 2, 100).
base_fee(main_cabin, europe_us, N, 200) :- N >= 3.

% -------- Oversize rules (Europe <-> U.S.) --------
oversize_fee(SizeIn, europe_us, 30)  :- SizeIn > 62, SizeIn =< 65.
oversize_fee(SizeIn, europe_us, 150) :- SizeIn > 65, SizeIn =< 115.
oversize_fee(SizeIn, europe_us, 0)   :- SizeIn =< 62.

% -------- Over-weight rules --------
% 50-53 lbs (all routes / all classes)
overweight_fee(W, 30)  :- W > 50, W =< 53.
% 53-70 lbs (Europe <-> U.S.)
overweight_fee(W, 100) :- W > 53, W =< 70.
% =<50 lbs -> no overweight fee
overweight_fee(W, 0)   :- W =< 50.

% choose the higher of the two extras
extra_fee(BagId, Fee) :-
    bag(BagId, _L,_W,_H,Weight),
    size_sum(BagId, Sum),
    route(roma,'salt_lake_city', Route),
    oversize_fee(Sum, Route, OSFee),
    overweight_fee(Weight, OWFee),
    Fee is max(OSFee, OWFee).

/*********************************************************************
   Facts describing the concrete case
*********************************************************************/
class(main_cabin).
ticket_price(608).

% bag(Id, Length, Width, Height, Weight)
bag(1, 21, 14,  6,  7).
bag(2, 38, 13, 12, 52).
bag(3, 38, 13, 14, 65).
bag(4, 38, 25, 14, 56).
bag(5, 39, 20, 12, 53).

% helper: total outside dimensions
size_sum(Id, Sum) :-
    bag(Id,L,W,H,_),
    Sum is L+W+H.

% carry-on test (=<22*14*9 inches)
carry_on(Id) :-
    bag(Id,L,W,H,_),
    L =< 22, W =< 14, H =< 9.

% checked_bag(+Id, -CheckedIndex)
% builds the list of checked bags in ascending Id order
checked_bag(Id, Index) :-
    findall(B, (bag(B,_,_,_,_), \+ carry_on(B)), Bs),
    nth1(Index, Bs, Id).

% fee for a particular checked bag
bag_total_fee(Id, Total) :-
    checked_bag(Id, Index),
    class(Class),
    route(roma,'salt_lake_city', Route),
    base_fee(Class, Route, Index, Base),
    extra_fee(Id, Extra),
    Total is Base + Extra.

% sum all bag fees
all_bag_fees(Sum) :-
    findall(F, (bag_total_fee(_,F)), Fees),
    sum_list(Fees, Sum).

% overall total cost
total_cost(Total) :-
    all_bag_fees(BagCost),
    ticket_price(Ticket),
    Total is Ticket + BagCost.

/*********************************************************************
   Query - prints the total
*********************************************************************/
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.