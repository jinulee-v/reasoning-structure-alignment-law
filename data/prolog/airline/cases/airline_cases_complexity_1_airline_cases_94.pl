/* ------------  Rules that encode the statutes (domestic / Business) ------------- */

% oversize_fee(+SizeSum, -Fee)
oversize_fee(Size, 0)   :- Size =< 62.
oversize_fee(Size, 30)  :- Size  > 62, Size =< 65.
oversize_fee(Size, 200) :- Size  > 65, Size =< 115.

% overweight_fee(+Weight, -Fee)
overweight_fee(W, 0)   :- W =< 50.
overweight_fee(W, 30)  :- W  > 50, W =< 53.
overweight_fee(W, 100) :- W  > 53, W =< 70.
overweight_fee(W, 200) :- W  > 70, W =< 100.

% checked_bag_base_fee(+Index, -Fee)   (Business Class - domestic)
checked_bag_base_fee(Index, 0)   :- Index =< 2.          % 1st - 2nd bags free
checked_bag_base_fee(3,     150).
checked_bag_base_fee(Index, 200) :- Index  > 3.          % 4th bag and up

/* --------------------  Facts that encode Michael's bags  ------------------------ */
/* We only list the CHECKED bags; his carry-on backpack is free and omitted.        */
/* bag(Index, Length, Width, Height, Weight)                                        */

bag(1, 34, 20,  9, 52).
bag(2, 38, 17, 13, 73).
bag(3, 37, 18, 10, 87).
bag(4, 34, 23, 10, 56).
bag(5, 34, 20,  9, 51).
bag(6, 53, 30, 31, 51).
bag(7, 40, 19, 13, 52).

/* --------------  Derived predicates to compute every bag's cost  ---------------- */

size_sum(L, W, H, S) :- S is L + W + H.

higher(X,Y,X) :- X >= Y.
higher(X,Y,Y) :- Y >  X.

bag_total_fee(Index, TotalFee) :-
    bag(Index,L,W,H,Weight),
    size_sum(L,W,H,Size),
    oversize_fee(Size, OFee),
    overweight_fee(Weight, WtFee),
    higher(OFee, WtFee, OWFee),        % only the higher of the two applies
    checked_bag_base_fee(Index, Base), % standard checked-bag fee
    TotalFee is Base + OWFee.

/* --------------------------  Overall trip cost  --------------------------------- */

ticket_price(54).

total_cost(Total) :-
    findall(F, bag_total_fee(_,F), Fees),
    sumlist(Fees, BagsTotal),
    ticket_price(Tix),
    Total is BagsTotal + Tix.

/* -----------------------------  Query block  ------------------------------------ */

:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.