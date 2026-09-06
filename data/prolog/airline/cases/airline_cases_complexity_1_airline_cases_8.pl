:- format("~w~n", ["Label: 3183"]).
/* ===================================================================
   Case:  William - First Class   Hong Kong  ->  Las Vegas
   Goal:  compute total trip cost (ticket + all luggage charges)
   =================================================================== */

/* ----------------------  Trip-specific facts  ---------------------- */

/* published ticket price */
flight_cost(1413).

/* passenger's pieces - bag(Id,Length,Width,Height,Weight)            */
/* (bag #1 is his carry-on and is therefore NOT in the checked list)  */
bag(1,20,11, 8,  8).       /* carry-on, ignored for charges */
bag(2,38,14,13, 51).
bag(3,49,27,25, 70).
bag(4,45,30,22, 83).
bag(5,37,13,13, 53).
bag(6,47,28,22, 56).
bag(7,35,17,11, 64).
bag(8,33,20,12, 53).

/* Ids of the bags that must be checked */
checked_bag_ids([2,3,4,5,6,7,8]).

/* ----------------------  Statutory parameters  --------------------- */

/* bag fees for this route ('to / from ... Hong Kong ...') - First Class   */
bag_fee(Idx,0)   :- Idx =< 3.           /* 1st-3rd bags complimentary  */
bag_fee(Idx,200) :- Idx >= 4.           /* 4th bag and beyond          */

/* size surcharge - Hong Kong / China region                           */
oversize_fee(Sum,Fee) :-
          ( Sum =< 62          -> Fee = 0
          ; Sum =< 65          -> Fee = 30
          ; Sum =< 115         -> Fee = 200 ).

/* overweight surcharge - Hong Kong / China region                    */
/* 'Thresh' is 70 lb for a complimentary bag, 50 lb for a charged bag  */
overweight_fee(W,Thresh,Fee) :-
          ( W =< Thresh        -> Fee = 0
          ; W =< 53            -> Fee = 30
          ; W =< 70            -> Fee = 100
          ; W =< 100           -> Fee = 450 ).

/* penalty that applies to a bag: higher of over-size vs over-weight   */
penalty(BagId,comp,Pen) :-
          bag(BagId,L,W,H,WT),
          Sum is L+W+H,
          oversize_fee(Sum,OS),
          overweight_fee(WT,70,OW),
          Pen is max(OS,OW).

penalty(BagId,charged,Pen) :-
          bag(BagId,L,W,H,WT),
          Sum is L+W+H,
          oversize_fee(Sum,OS),
          overweight_fee(WT,50,OW),
          Pen is max(OS,OW).

/* ----------------------  Helper predicates  ------------------------ */

/* choose three different elements (A < B < C) from a list            */
choose_three(List,A,B,C) :-
          append(_, [A|Tail1], List),
          append(_, [B|Tail2], Tail1),
          member(C, Tail2),
          A < B, B < C.

/* build ordered list: complimentary bags first, the rest afterwards  */
ordered_list(A,B,C,Ordered) :-
          checked_bag_ids(All),
          select(A,All,R1),
          select(B,R1,R2),
          select(C,R2,R3),
          Ordered = [A,B,C|R3].

/* ----------------------  Cost computation -------------------------- */

cost_for_choice(A,B,C,Total) :-
          ordered_list(A,B,C,Ord),
          cost_bags(Ord,1,BagCost,PenCost),
          flight_cost(Tix),
          Total is Tix + BagCost + PenCost.

/* walk through ordered list accumulating base fees and penalties      */
cost_bags([],_,0,0).
cost_bags([Bag|Bs],Idx,FeeTot,PenTot) :-
          (Idx =< 3 -> Type = comp ; Type = charged),
          bag_fee(Idx,Base),
          penalty(Bag,Type,Pen),
          Next is Idx + 1,
          cost_bags(Bs,Next,FeeRest,PenRest),
          FeeTot is Base + FeeRest,
          PenTot is Pen + PenRest.

/* minimal total over all ways of selecting the 3 complimentary bags   */
total_cost(Min) :-
          checked_bag_ids(L),
          findall(T,
                  ( choose_three(L,A,B,C),
                    cost_for_choice(A,B,C,T) ),
                  Totals),
          min_list(Totals,Min).

/* ----------------------  Query & output  --------------------------- */
:- total_cost(Total), format('Total cost: ~w~n',[Total]).
:- halt.