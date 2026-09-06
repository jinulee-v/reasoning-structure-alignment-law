/* ----------  Statutory rules that matter for this case --------------- */

% route for this itinerary
route(within_us).

% carry-on / personal-item size limits
carryon_dims(22,14,9).
personal_dims(18,14,8).

% checked-bag fees (Premium Economy, within U.S.)
bag_fee(Index,0)  :- Index =< 2.           % 1st & 2nd bag free
bag_fee(3,150).
bag_fee(Index,200):- Index >= 4.

% oversize fees, within U.S.
oversize_fee(Size,0)   :- Size =< 62.
oversize_fee(Size,30)  :- Size  > 62, Size =< 65.
oversize_fee(Size,200) :- Size  > 65, Size =< 115.

% overweight fees, within U.S.
overweight_fee(W,0)    :- W =< 50.
overweight_fee(W,30)   :- W  > 50, W =< 53.
overweight_fee(W,100)  :- W  > 53, W =< 70.

% choose the higher of overweight / oversize
extra_fee(Size,Weight,Fee):-
    oversize_fee(Size,O),
    overweight_fee(Weight,W),
    (O >= W -> Fee = O ; Fee = W).

/* --------------------  The case facts  ------------------------------ */

% item(ID, length, width, height, weight).
item(1,22,11, 7,12).
item(2,38,20,13,52).
item(3,38,12,13,56).
item(4,34,16,14,63).
item(5,37,13,14,51).
item(6,33,22, 9,51).
item(7,51,32,31,65).
item(8,53,30,25,56).

/* ----------------  Helper predicates  -------------------------------- */

size_sum(L,W,H,S) :- S is L+W+H.

is_carryon(ID) :-
    item(ID,L,W,H,_),
    carryon_dims(LC,WC,HC),
    L =< LC, W =< WC, H =< HC.

is_personal(ID) :-
    item(ID,L,W,H,_),
    personal_dims(LP,WP,HP),
    L =< LP, W =< WP, H =< HP.

/* --------------  Determine which items are checked ------------------- */

carryon_item(ID) :- is_carryon(ID), !.      % take the first that fits
checked_item(ID) :-
    item(ID,_,_,_,_),
    \+ carryon_item(ID).

checked_items(List) :-
    findall(ID,checked_item(ID),Unsorted),
    sort(Unsorted,List).                    % ascending order (2..8)

/* -------------  Cost of each checked bag ----------------------------- */

bag_cost(Index,ID,Cost) :-
    item(ID,L,W,H,Weight),
    size_sum(L,W,H,Size),
    bag_fee(Index,BFee),
    extra_fee(Size,Weight,EFee),
    Cost is BFee + EFee.

/* -------------  Total baggage cost ----------------------------------- */

total_baggage_cost(Total) :-
    checked_items(IDs),
    bag_costs(1,IDs,Total).

bag_costs(_,[],0).
bag_costs(N,[ID|Rest],Total) :-
    bag_cost(N,ID,Cost1),
    N1 is N+1,
    bag_costs(N1,Rest,CostRest),
    Total is Cost1 + CostRest.

/* -------------  Overall trip cost ------------------------------------ */

flight_cost(119).

total_cost(Total) :-
    total_baggage_cost(BagCost),
    flight_cost(Flight),
    Total is BagCost + Flight.

/* --------------------  Query / output  ------------------------------- */

:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.