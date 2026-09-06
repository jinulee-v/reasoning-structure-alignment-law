/* ------------  Statutory rules (domestic U.S. flight, Premium Economy) ------------- */

/* base_checked_fee(NthBag, Fee) */
base_checked_fee(N, 0)   :- N =< 2.          % 1st-2nd bag free
base_checked_fee(3, 150).                    % 3rd bag
base_checked_fee(N, 200) :- N >= 4.          % 4th bag and beyond

/* oversize_fee(DimSum, Fee) - U.S / Canada / PR / USVI */
oversize_fee(D, 0)   :- D =< 62.
oversize_fee(D, 30)  :- D > 62, D =< 65.
oversize_fee(D, 200) :- D > 65, D =< 115.

/* overweight_fee(Weight, Fee) - U.S / Canada / PR / USVI */
overweight_fee(W, 0)   :- W =< 50.
overweight_fee(W, 30)  :- W > 50, W =< 53.
overweight_fee(W, 100) :- W > 53, W =< 70.
overweight_fee(W, 200) :- W > 70, W =< 100.

/* extra_fee is the higher of oversize vs overweight for that bag */
extra_fee(Dim, Wt, Fee) :-
    oversize_fee(Dim, OS),
    overweight_fee(Wt, OW),
    ( OS >= OW -> Fee = OS ; Fee = OW ).

/* -------------  Facts describing Jennifer's items  ----------------- */
/* bag(ID, Type, Length, Width, Height, Weight)   Type = personal | check  */

bag(1, personal, 18,14,7, 10).

bag(2, check, 52,29,25, 53).
bag(3, check, 38,15,10, 81).
bag(4, check, 38,17,10, 56).
bag(5, check, 39,25,15, 52).
bag(6, check, 52,31,27, 52).
bag(7, check, 47,30,22, 71).
bag(8, check, 52,31,28, 53).

ticket_price(182).

/* -----------  Helper predicates to number the checked bags ----------- */

checked_bag_ids(IDs) :-
    findall(ID, bag(ID, check,_,_,_,_), List),
    sort(List, IDs).

checked_index(ID, Index) :-
    checked_bag_ids(List),
    nth1(Index, List, ID).

/* cost for each checked bag = base fee (by index) + extra fee */
bag_cost(ID, Cost) :-
    bag(ID, check,L,W,H,Wt),
    Dim is L+W+H,
    checked_index(ID, N),
    base_checked_fee(N, BaseFee),
    extra_fee(Dim, Wt, Extra),
    Cost is BaseFee + Extra.

/* ----------------------  Total cost  ------------------------------- */

total_cost(Total) :-
    ticket_price(Ticket),
    findall(C, bag_cost(_,C), Costs),
    sum_list(Costs, BagsTotal),
    Total is Ticket + BagsTotal.

/* ----------------------  Query & output ----------------------------- */
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.