/* ----------  Facts describing Patricia's trip  ---------- */

flight_cost(96).
cabin(main_plus).
route(domestic).

/* bag(Id,Length,Width,Height,Weight) */
bag(1,18,14,9,12).
bag(2,38,12,13,82).
bag(3,50,31,24,91).
bag(4,36,15,13,52).
bag(5,46,26,20,52).
bag(6,46,30,24,53).
bag(7,47,25,18,54).
bag(8,38,13,13,61).
bag(9,37,15,12,51).
bag(10,35,20,10,64).
bag(11,38,15,12,52).

/* ----------  Statutory rules for this itinerary ---------- */

/* carry-on limits */
carry_on_max(22,14,9).

/* oversize fee: within U.S. */
oversize_fee(Sum,Fee) :-
    ( Sum =< 62  -> Fee = 0
    ; Sum =< 65  -> Fee = 30
    ; Sum =< 115 -> Fee = 200 ).

/* overweight fee: 50-lb limit for all Main Cabin / Main Plus bags */
overweight_fee(W,Fee) :-
    ( W =< 50  -> Fee = 0
    ; W =< 53  -> Fee = 30
    ; W =< 70  -> Fee = 100
    ; W =< 100 -> Fee = 200 ).

/* penalty is max of oversize vs overweight */
penalty(BagId,Pen) :-
    bag(BagId,L,W,H,Weight),
    Sum is L+W+H,
    oversize_fee(Sum,OS),
    overweight_fee(Weight,OW),
    (OS >= OW -> Pen = OS ; Pen = OW).

/* bag fees for Main Plus: one free bag, then standard fees */
bag_fee(1,0).
bag_fee(2,45).
bag_fee(3,150).
bag_fee(N,200) :- N>=4.

/* ----------  Helper predicates ---------- */

/* check if a bag qualifies as carry-on */
carry_on(Id) :-
    bag(Id,L,W,H,_),
    carry_on_max(MaxL,MaxW,MaxH),
    L=<MaxL, W=<MaxW, H=<MaxH.

/* collect all checked bag IDs (exclude carry-on) */
checked_bag_ids(List) :-
    findall(Id, (bag(Id,_,_,_,_), \+ carry_on(Id)), List).

/* choose one free bag */
choose_one(List,F) :-
    member(F,List).

/* place the free bag first, others follow */
ordered_list(F,Ordered) :-
    checked_bag_ids(All),
    select(F,All,Rest),
    Ordered = [F|Rest].

/* compute total for a particular free-bag choice */
cost_for_choice(F,Total) :-
    ordered_list(F,Ordered),
    cost_bags(Ordered,1,CostBags,Penalties),
    flight_cost(Flight),
    Total is Flight + CostBags + Penalties.

/* walk through ordered list accumulating fees */
cost_bags([],_,0,0).
cost_bags([Bag|Bs],Idx,CostSum,PenSum) :-
    bag_fee(Idx,Fee),
    penalty(Bag,Pen),
    NextIdx is Idx+1,
    cost_bags(Bs,NextIdx,CostRest,PenRest),
    CostSum is Fee + CostRest,
    PenSum  is Pen + PenRest.

/* compute minimal total cost */
total_cost(MinTotal) :-
    checked_bag_ids(L),
    findall(T,
            ( choose_one(L,F),
              cost_for_choice(F,T) ),
            Totals),
    min_list(Totals,MinTotal).

/* ----------  Query and output ---------- */
:- total_cost(Total), format('Total cost: ~w~n',[Total]).
:- halt.