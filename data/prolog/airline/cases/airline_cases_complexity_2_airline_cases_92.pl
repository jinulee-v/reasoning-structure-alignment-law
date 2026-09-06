/* ----------  Statutory rules needed for this case ---------- */

/* base_checked_fee(BagNumberInCheckedOrder, Fee)               */
/* Hong Kong  ->  U.S. | Main-Cabin                              */
/* 1st bag free, 2nd bag $100, 3rd+ bags $200                   */
base_checked_fee(1, 0).
base_checked_fee(2, 100).
base_checked_fee(N, 200) :- N >= 3.

/* oversize_fee(DimSum, Fee)  - Hong Kong rule set              */
oversize_fee(D, 0)        :- D =< 62.                 /* not oversize */
oversize_fee(D, 30)       :- D  > 62, D =< 65.
oversize_fee(D, 200)      :- D  > 65, D =< 115.

/* overweight_fee(Weight, Fee) - Hong Kong rule set             */
overweight_fee(W, 0)      :- W =< 50.
overweight_fee(W, 30)     :- W  > 50, W =< 53.
overweight_fee(W, 100)    :- W  > 53, W =< 70.
overweight_fee(W, 450)    :- W  > 70, W =< 100.

/* extra_fee is the higher of over-size vs over-weight          */
extra_fee(Dim, W, Fee) :-
    oversize_fee(Dim, OS),
    overweight_fee(W, OW),
    (OS >= OW -> Fee = OS ; Fee = OW).

/* ----------  Facts about Susan's items  --------------------- */
/* bag(Id, Length, Width, Height, Weight).                      */
bag(1, 20, 11,  6,  5).
bag(2, 38, 13, 13, 52).
bag(3, 44, 23, 15, 66).
bag(4, 36, 15, 13, 99).
bag(5, 34, 21, 10, 70).
bag(6, 36, 19, 17, 95).
bag(7, 51, 25, 26, 53).
bag(8, 39, 16, 13, 60).
bag(9, 47, 28, 27, 60).
bag(10,44, 21, 17, 61).
bag(11,40, 20, 13, 55).

/* Item 1 is used as the one free carry-on, so all others are   */
/* checked.  We pre-declare their checked order 2-11.           */
checked_order([2,3,4,5,6,7,8,9,10,11]).

/* ----------  Computing bag cost ------------------------------ */

bag_cost(Id, Position, Cost) :-
    bag(Id, L, Wd, H, Weight),
    DimSum is L + Wd + H,
    extra_fee(DimSum, Weight, Extra),
    base_checked_fee(Position, Base),
    Cost is Base + Extra.

/* total_bag_fees(Total)                                        */
total_bag_fees(Total) :-
    checked_order(Ids),
    findall(C,
            (nth1(Pos, Ids, Id),
             bag_cost(Id, Pos, C)),
            Cs),
    sum_list(Cs, Total).

/* Flight ticket                                                */
ticket_cost(1394).

/* total_cost(Total)                                            */
total_cost(Total) :-
    ticket_cost(T),
    total_bag_fees(Bags),
    Total is T + Bags.

/* ----------  Produce answer ---------------------------------- */
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.