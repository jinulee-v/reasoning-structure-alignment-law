/* ---------------------------
   Statutory rules - simplified
   (only those applying to this case)
   --------------------------- */

/* 1.  Two complimentary checked bags for Business Class */
complimentary_bags(business,2).

/* 2.  Base checked-bag fee (bags beyond complimentary)            */
/*     Route: Haiti (Caribbean)  <->  U.S.  =  $200 for 3rd bag + */
bag_base_fee(Index, Fee) :-
    complimentary_bags(business, Free),
    Index =< Free,               Fee = 0.
bag_base_fee(Index, Fee) :-
    complimentary_bags(business, Free),
    Index  > Free,               Fee = 200.

/* 3.  Over-WEIGHT fee (Caribbean <-> U.S.)                         */
overweight_fee(W, Fee) :-
    W =< 50                     , Fee = 0.
overweight_fee(W, 30)           :- W  > 50, W =< 53.
overweight_fee(W, 100)          :- W > 53, W =< 70.
overweight_fee(W, 200)          :- W > 70, W =< 100.

/* 4.  Over-SIZE fee (Caribbean <-> U.S.)                           */
oversize_fee(S, 0)   :- S =< 62.
oversize_fee(S, 30)  :- S > 62, S =< 65.
oversize_fee(S, 200) :- S > 65, S =< 115.

/* 5.  Penalty on a bag is the HIGHER of the two                    */
penalty_fee(Weight, Size, Fee) :-
    overweight_fee(Weight, WFee),
    oversize_fee(Size,   SFee),
    Fee is max(WFee,SFee).

/* ---------------------------
   Case facts - William
   --------------------------- */

flight_ticket(98).

/* checkedbag(Index, Weight(lbs), SizeLinear(inches)) */
checkedbag(1, 99, 115).
checkedbag(2, 52,  65).
checkedbag(3, 52,  81).
checkedbag(4, 52,  65).
checkedbag(5, 99,  65).
checkedbag(6, 68,  96).
checkedbag(7, 75, 111).

/* ---------------------------
   Calculations
   --------------------------- */

bag_total_cost(Index, Cost) :-
    checkedbag(Index, W, S),
    bag_base_fee(Index, Base),
    penalty_fee(W, S, Pen),
    Cost is Base + Pen.

all_bags_cost(Total) :-
    findall(C, bag_total_cost(_,C), List),
    sum_list(List, Total).

total_cost(Total) :-
    all_bags_cost(Bags),
    flight_ticket(Tix),
    Total is Bags + Tix.

/* ---------------------------
   Query & output
   --------------------------- */
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.