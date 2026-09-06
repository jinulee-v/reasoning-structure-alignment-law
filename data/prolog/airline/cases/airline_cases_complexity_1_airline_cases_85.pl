/* ---  Statutory rules that are relevant to this case  --- */

/* The journey is between the U.S. and South America (except Colombia / Ecuador / Peru / Guyana / Suriname) */
route(us_samerica).

/* Passenger's booking information */
ticket_price(645).
cabin_class(basic_economy).

/* ----  BASE-LINE CHECKED-BAG FEES (South America  - Basic Economy)  ---- */
base_bag_fee(1,basic_economy,us_samerica,60).        /* 1st bag  */
base_bag_fee(2,basic_economy,us_samerica,100).       /* 2nd bag  */
base_bag_fee(N,basic_economy,us_samerica,200) :-     /* 3rd bag + */
        N>=3.

/* ----  OVERWEIGHT FEES (South America  - Basic Economy)  ---- */
overweight_fee(Weight,us_samerica,0)   :- Weight =< 53.
overweight_fee(Weight,us_samerica,100) :- Weight > 53, Weight =< 70.
overweight_fee(Weight,us_samerica,200) :- Weight > 70, Weight =< 100.

/* ----  OVERSIZE FEES (South America)  ---- */
oversize_fee(Dim,us_samerica,0)   :- Dim =< 62.
oversize_fee(Dim,us_samerica,30)  :- Dim > 62 , Dim =< 65.
oversize_fee(Dim,us_samerica,150) :- Dim > 65 , Dim =< 115.

/* Take the higher of the two special-handling fees */
higher_fee(F1,F2,F1) :- F1 >= F2.
higher_fee(F1,F2,F2) :- F2 >  F1.

/* ----  DANIEL'S BAGS (personal item excluded)  ----
   checked_bag(Seq#, DimSumInches, WeightLbs)
*/
checked_bag(1,106,66).
checked_bag(2,64 ,98).
checked_bag(3,64 ,68).
checked_bag(4,80 ,62).
checked_bag(5,63 ,99).

/* ----  TOTAL FEE FOR ONE CHECKED BAG  ---- */
bag_total_cost(Seq,Total) :-
        checked_bag(Seq,Dim,Weight),
        cabin_class(Class),
        route(Route),
        base_bag_fee(Seq,Class,Route,BaseFee),
        oversize_fee(Dim,Route,OverSizeFee),
        overweight_fee(Weight,Route,OverWeightFee),
        higher_fee(OverSizeFee,OverWeightFee,Extra),
        Total is BaseFee + Extra.

/* ----  SUM ALL COSTS (bags + ticket)  ---- */
total_cost(Total) :-
        ticket_price(Ticket),
        findall(C,bag_total_cost(_,C),Cs),
        sum_list(Cs,BagsTotal),
        Total is Ticket + BagsTotal.

/* ------------  QUERY  ------------ */
:- total_cost(Total), format('Total cost: ~w~n',[Total]).
:- halt.