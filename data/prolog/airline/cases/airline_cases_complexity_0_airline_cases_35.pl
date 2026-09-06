/* ----------  STATUTORY RULES (relevant excerpts only)  ---------- */

/* overweight fees for the route "To / from Japan" ----------------- */
overweight_fee(Weight, 450) :- Weight > 70,   Weight =< 100.   /* 70-100 lb */
overweight_fee(Weight, 100) :- Weight > 53,   Weight =< 70.    /* 53-70  lb */
overweight_fee(Weight,  30) :- Weight > 50,   Weight =< 53.    /* 50-53  lb */
overweight_fee(Weight,   0) :- Weight =< 50.                   /* =<50   lb */

/* oversize fees for the same route --------------------------------*/
oversize_fee(Dim, 200) :- Dim >  65, Dim =< 115.               /* >65-115 in */
oversize_fee(Dim,  30) :- Dim >  62, Dim =<  65.               /* >62-65  in */
oversize_fee(Dim,   0) :- Dim =< 62.                           /* =<62    in */

/* the higher of oversize vs. overweight is charged ---------------*/
extra_fee(BagNo, Fee) :-
    bag(BagNo, Weight, Dim),
    overweight_fee(Weight, F1),
    oversize_fee(Dim,     F2),
    Fee is max(F1, F2).

/* Premium-Economy: 1st & 2nd checked bags free; 3rd & 4th cost $200 */
base_bag_fee(BagNo, 0)   :- BagNo =< 2.
base_bag_fee(BagNo, 200) :- BagNo  > 2.

/* --------------------  FACTS FOR THIS CASE  ----------------------*/
/* bag(No, Weight(lbs), Size (L+W+H inches))   */
/* (order chosen so the two heaviest bags get the free base fee)    */
bag(1, 81,  65).
bag(2, 95, 104).
bag(3, 52,  63).
bag(4, 51,  64).

/* flight ticket price -------------------------------------------- */
ticket_cost(532).

/* -----------------  AGGREGATE COST CALCULATIONS  ---------------- */
bag_cost(BagNo, Cost) :-
    base_bag_fee(BagNo, Base),
    extra_fee(BagNo, Extra),
    Cost is Base + Extra.

total_bag_cost(Total) :-
    findall(C, (bag(N,_,_), bag_cost(N, C)), Cs),
    sum_list(Cs, Total).

total_cost(Total) :-
    total_bag_cost(Bags),
    ticket_cost(Ticket),
    Total is Bags + Ticket.

/* ------------------------  QUERY  --------------------------------*/
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.