:- format("~w~n", ["Label: 5162"]).
/* =========================================================
   American Airlines baggage calculation
   Case: Mary - Business Class, Tokyo (Japan) -> Dallas (U.S.)
   ========================================================= */

/* ---------------  Ticket price  -------------------------- */
flight_cost(402).

/* ---------------  Checked-bag data  ----------------------- */
/* bag(Id,Length,Width,Height,Weight) - carry-on (bag 1) omitted */
bag(2,33,20,10,97).
bag(3,54,34,26,63).
bag(4,34,22, 9,87).
bag(5,44,27,21,98).
bag(6,48,32,27,99).
bag(7,47,29,19,74).
bag(8,33,20,12,56).
bag(9,34,16,14,53).
bag(10,40,22,12,70).
bag(11,35,20, 9,83).

/* list of all checked-bag IDs */
checked_bag_ids([2,3,4,5,6,7,8,9,10,11]).

/* ---------------  Statutory rules (to / from Japan)  ------ */

/* dimensional sum */
dims_sum(L,W,H,S) :- S is L+W+H.

/* oversize fees : China / Japan / S. Korea / HK / India / AUS / NZ */
oversize_fee(Sum,Fee) :-
        (  Sum =< 62      -> Fee = 0
        ;  Sum =< 65      -> Fee = 30
        ;  Sum =< 115     -> Fee = 200 ).

/* overweight fees : to / from Japan (complimentary-threshold variable) */
overweight_fee(W,Thresh,Fee) :-
        (  W =< Thresh    -> Fee = 0
        ;  W =< 53        -> Fee = 30
        ;  W =< 70        -> Fee = 100
        ;  W =< 100       -> Fee = 450 ).

/* penalty = higher of oversize vs overweight */
penalty(BagId,comp,Pen) :-
        bag(BagId,L,W,H,Weight),
        dims_sum(L,W,H,Sum),
        oversize_fee(Sum,OS),
        overweight_fee(Weight,70,OW),      % complimentary => 70-lb limit
        Pen is max(OS,OW).

penalty(BagId,charged,Pen) :-
        bag(BagId,L,W,H,Weight),
        dims_sum(L,W,H,Sum),
        oversize_fee(Sum,OS),
        overweight_fee(Weight,50,OW),      % charged bag => 50-lb limit
        Pen is max(OS,OW).

/* Business Class bag fees : to / from Japan */
bag_fee(1,0).
bag_fee(2,0).
bag_fee(N,200) :- N>=3.

/* ---------------  Helper predicates  ---------------------- */

/* choose 2 distinct elements (F1 < F2) from a list */
choose_two(List,F1,F2) :-
        append(_,[F1|Tail],List),
        member(F2,Tail).

/* place the 2 freebies first, keep original relative order for rest */
ordered_list(F1,F2,Ordered) :-
        checked_bag_ids(All),
        select(F1,All,Rest1),
        select(F2,Rest1,Rest),
        Ordered = [F1,F2|Rest].

/* compute cost for a particular selection of free bags */
cost_for_choice(F1,F2,TotalCost) :-
        ordered_list(F1,F2,Ordered),
        bags_cost(Ordered,1,BagsFees,BagsPenalties),
        flight_cost(Flight),
        TotalCost is Flight + BagsFees + BagsPenalties.

/* walk through ordered list accumulating base fees & penalties */
bags_cost([],_,0,0).
bags_cost([Bag|Bs],Idx,CostSum,PenSum) :-
        (Idx =< 2 -> Kind = comp ; Kind = charged),
        bag_fee(Idx,Base),
        penalty(Bag,Kind,Pen),
        Next is Idx+1,
        bags_cost(Bs,Next,CostRest,PenRest),
        CostSum is Base + CostRest,
        PenSum  is Pen  + PenRest.

/* ---------------  Minimise over all ways to pick 2 freebies */
total_cost(MinTotal) :-
        checked_bag_ids(L),
        findall(T,
                ( choose_two(L,F1,F2),
                  cost_for_choice(F1,F2,T)),
                Totals),
        min_list(Totals,MinTotal).

/* ---------------  Query & display  ------------------------ */
:- total_cost(Total), format('Total cost: ~w~n',[Total]).
:- halt.