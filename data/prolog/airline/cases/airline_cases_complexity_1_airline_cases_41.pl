/* ---------  Statutory rules that are relevant to this case  --------- */

/*  Carry-on is free - no rule needed (one of the bags will be flagged
    as carry-on in the case-facts section).                             */

/*  Base checked-bag fees on a Basic-Economy itinerary
    Japan (Asia list)   --->    U.S.                                     */
base_fee(BagNum, 75) :- BagNum =:= 1.
base_fee(BagNum, 100) :- BagNum =:= 2.
base_fee(BagNum, 200) :- BagNum >= 3.

/*  Oversize fees (Japan <-> U.S.)
    size = L+W+H                                                         */
size_fee(DimSum, 0)               :- DimSum =< 62.
size_fee(DimSum, 30)              :- DimSum  > 62, DimSum =< 65.
size_fee(DimSum, 200)             :- DimSum  > 65, DimSum =< 115.

/*  Over-weight fees (Japan <-> U.S.)                                      */
weight_fee(W, 0)                  :- W =< 50.
weight_fee(W, 30)                 :- W  > 50, W =< 53.
weight_fee(W, 100)                :- W  > 53, W =< 70.
weight_fee(W, 450)                :- W  > 70, W =< 100.

/*  The statute says "the higher fee between oversize and overweight
    applies (in addition to the base checked-bag fee)"                   */
extra_fee(BagIndex, Extra) :-
    bag(BagIndex, L, Wd, H, Weight),
    DimSum is L + Wd + H,
    size_fee(DimSum, SF),
    weight_fee(Weight, WF),
    Extra is max(SF, WF).

/* ---------  Facts describing Elizabeth's situation  --------- */

/* bag(Index, Length, Width, Height, Weight)                             */
bag(1,21,12, 8, 10).   /* carry-on   */
bag(2,34,18,12, 56).
bag(3,36,19, 9, 76).
bag(4,34,17,13, 73).
bag(5,41,26,17, 90).
bag(6,35,19,16, 86).
bag(7,33,23, 9, 53).
bag(8,34,21,10, 58).

/* Bag #1 is used as the free carry-on; the rest are checked.            */
carry_on(1).

/* checked_bag(Index, SequenceNumber) - order after the carry-on         */
checked_bag(2,1).
checked_bag(3,2).
checked_bag(4,3).
checked_bag(5,4).
checked_bag(6,5).
checked_bag(7,6).
checked_bag(8,7).

/* ---------  Cost calculations  --------- */

checked_bag_total_fee(Index, Fee) :-
    checked_bag(Index, Seq),
    base_fee(Seq, Base),
    extra_fee(Index, Extra),
    Fee is Base + Extra.

sum_checked_bag_fees(Sum) :-
    findall(F, checked_bag_total_fee(_,F), Fs),
    sum_list(Fs, Sum).

ticket_price(395).

total_cost(Total) :-
    ticket_price(T),
    sum_checked_bag_fees(Bags),
    Total is T + Bags.

/* ---------  Query requested by the assignment  --------- */
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.