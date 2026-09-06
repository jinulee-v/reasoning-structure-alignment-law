/*  ------------  Statutory rules (relevant extracts)  ------------  */

/*  Over-weight fees for flights to / from India (all cabins)  */
overweight_fee(Weight, 450) :- Weight > 70, Weight =< 100, !.
overweight_fee(Weight, 100) :- Weight > 53, Weight =< 70, !.
overweight_fee(Weight,  30) :- Weight > 50, Weight =< 53, !.
overweight_fee(Weight,   0) :- Weight =< 50.

/*  Over-size fees for flights to / from India (all cabins)  */
oversize_fee(Size, 200) :- Size > 65, Size =< 115, !.
oversize_fee(Size,  30) :- Size > 62, Size =< 65, !.
oversize_fee(Size,   0) :- Size =< 62.

/*  Checked-bag 'count' fees for a First Class passenger  
    (to / from India): bags 1-3 free, bag 4+ $200                */
bag_count_fee(Index, 0)   :- Index =< 3, !.
bag_count_fee(Index, 200) :- Index  > 3.

/*  ------------  Facts describing Daniel's trip  ------------  */

/*  bag(Number, Weight_lbs, Size_in) - size is L+W+H             */
bag(1,  64, 101).   /* 47x29x25 in  */
bag(2,  90,  65).   /* 35x19x11 in  */
bag(3, 100, 111).   /* 49x32x30 in  */
bag(4,  96,  64).   /* 35x17x12 in  */

/*  Flight ticket price                                          */
ticket_price(576).

/*  ------------  Derived calculations  ------------  */

/*  Cost for one checked bag = count-fee + higher of overweight / oversize  */
bag_total_cost(Index, Cost) :-
    bag(Index, W, S),
    overweight_fee(W, OW),
    oversize_fee(S, OS),
    (OW >= OS -> OverCost = OW ; OverCost = OS),
    bag_count_fee(Index, CountCost),
    Cost is OverCost + CountCost.

/*  Sum fees for all checked bags                                */
total_bags_cost(Total) :-
    findall(C, bag_total_cost(_, C), Cs),
    sumlist(Cs, Total).

/*  Grand total = ticket + all bag fees                          */
total_cost(Grand) :-
    ticket_price(T),
    total_bags_cost(Bags),
    Grand is T + Bags.

:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.