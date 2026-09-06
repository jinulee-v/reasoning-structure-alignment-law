/*======================================================================
   American Airlines baggage-fee calculator
   Itinerary: Chengdu (China)  ->  Minneapolis (U.S.)
   Cabin   : First Class
   Passenger: Elizabeth
======================================================================*/

/* -------------------------------------------------------------------
   Ticket price
-------------------------------------------------------------------*/
flight_cost(923).

/* -------------------------------------------------------------------
   Checked bags
   bag(Id,Length,Width,Height,Weight)
-------------------------------------------------------------------*/
bag(2, 33,16,14,57).
bag(3, 34,20,10,54).
bag(4, 34,18,13,51).
bag(5, 37,17,10,85).
bag(6, 48,22,24,94).
bag(7, 43,23,17,59).
bag(8, 34,16,13,65).
bag(9, 38,12,13,61).
bag(10,34,20,14,85).
bag(11,45,26,17,53).

checked_bag_ids([2,3,4,5,6,7,8,9,10,11]).

/* -------------------------------------------------------------------
   Helper - sum of dimensions
-------------------------------------------------------------------*/
dim_sum(L,W,H,S) :- S is L+W+H.

/* -------------------------------------------------------------------
   Oversize fees  (China / Japan / S. Korea / Hong-Kong / India / Aus / NZ)
-------------------------------------------------------------------*/
oversize_fee(Sum,Fee) :-
       (   Sum =< 62      -> Fee = 0
       ;   Sum =< 65      -> Fee = 30
       ;   Sum =< 115     -> Fee = 200 ).

/* -------------------------------------------------------------------
   Over-weight fees   (all classes, same region as above)
   Thresh = free weight allowance for the bag:
            70 lb for complimentary bags
            50 lb for paid bags
-------------------------------------------------------------------*/
overweight_fee(W,Thresh,Fee) :-
       (   W =< Thresh -> Fee = 0
       ;   W =< 53     -> Fee = 30
       ;   W =< 70     -> Fee = 100
       ;   W =< 100    -> Fee = 450 ).

/* -------------------------------------------------------------------
   Penalty for a bag = higher of oversize vs overweight fee
-------------------------------------------------------------------*/
penalty(BagId,comp,Pen) :-
       bag(BagId,L,W,H,Wt),
       dim_sum(L,W,H,DimSum),
       oversize_fee(DimSum,OS),
       overweight_fee(Wt,70,OW),
       Pen is max(OS,OW).

penalty(BagId,charged,Pen) :-
       bag(BagId,L,W,H,Wt),
       dim_sum(L,W,H,DimSum),
       oversize_fee(DimSum,OS),
       overweight_fee(Wt,50,OW),
       Pen is max(OS,OW).

/* -------------------------------------------------------------------
   Checked-bag base fee by ordinal position (First Class, this route)
-------------------------------------------------------------------*/
bag_fee(1,0).
bag_fee(2,0).
bag_fee(3,0).
bag_fee(N,200) :- N >= 4.

/* -------------------------------------------------------------------
   Pick any 3 distinct elements from a list (A < B < C in the list order)
-------------------------------------------------------------------*/
choose_three(List,A,B,C) :-
       append(_, [A|T1], List),
       append(_, [B|T2], T1),
       member(C, T2).

/* -------------------------------------------------------------------
   Put the 3 complimentary bags first, keep remaining order arbitrary
-------------------------------------------------------------------*/
ordered_list(A,B,C,Ordered) :-
       checked_bag_ids(All),
       select(A,All,R1),
       select(B,R1,R2),
       select(C,R2,Remainder),
       Ordered = [A,B,C|Remainder].

/* -------------------------------------------------------------------
   Cost for a particular choice of complimentary bags
-------------------------------------------------------------------*/
cost_for_choice(A,B,C,Total) :-
       ordered_list(A,B,C,Ordered),
       cost_bags(Ordered,1,FeeSum,PenSum),
       flight_cost(Fare),
       Total is Fare + FeeSum + PenSum.

/* Recursive walk over the ordered list */
cost_bags([],_,0,0).
cost_bags([Bag|Bs],Idx,FeeSum,PenSum) :-
       (Idx =< 3 -> Kind = comp ; Kind = charged),
       bag_fee(Idx,BFee),
       penalty(Bag,Kind,Pen),
       NextIdx is Idx + 1,
       cost_bags(Bs,NextIdx,RestFee,RestPen),
       FeeSum is BFee + RestFee,
       PenSum is Pen + RestPen.

/* -------------------------------------------------------------------
   Overall minimum total across all ways to pick 3 freebies
-------------------------------------------------------------------*/
total_cost(MinTotal) :-
       checked_bag_ids(Ids),
       findall(T,
              (choose_three(Ids,A,B,C),
               cost_for_choice(A,B,C,T)),
              Totals),
       min_list(Totals,MinTotal).

/* -------------------------------------------------------------------
   Query & output
-------------------------------------------------------------------*/
compute_total(Cost) :- total_cost(Cost).
:- compute_total(Cost), format('Total cost: ~w~n', [Cost]), halt.