/* =========================================================
   American Airlines - baggage cost calculator
   Case: Jennifer (Austin, U.S.  ->  Doha, Qatar), First Class
   ========================================================= */

/* ----------------  Ticket  ---------------- */
flight_cost(1165).

/* ----------------  Checked bags ------------
   Format: bag(Id,Length,Width,Height,Weight).               */
bag(2, 55,32,27,53).
bag(3, 37,15,12,53).
bag(4, 37,18,10,51).
bag(5, 42,24,14,52).
bag(6, 48,23,25,68).
bag(7, 35,19,10,55).
bag(8, 36,14,13,66).
bag(9, 44,26,16,56).
bag(10,37,27,13,52).
bag(11,35,20, 9,53).

/* list of all checked-bag IDs */
checked_bag_ids([2,3,4,5,6,7,8,9,10,11]).

/* ==============  Statutory rules  ======================== */

/* -------- size (sum of dimensions) -------- */
dims_sum(L,W,H,S) :- S is L+W+H.

/* -------- oversize fee : "Europe / Israel / Qatar" zone -- */
oversize_fee(Sum,Fee) :-
      (  Sum =< 62          -> Fee = 0
      ;  Sum =< 65          -> Fee = 30
      ;  Sum =< 115         -> Fee = 150 ).

/* -------- overweight fee (parametrised by free-weight) ----
   Thresh = 70 lb for complimentary bags, 50 lb for charged  */
overweight_fee(W,Thresh,Fee) :-
      (  W =< Thresh        -> Fee = 0
      ;  W =< 53            -> Fee = 30
      ;  W =< 70            -> Fee = 100  ).

/* -------- penalty for one bag - higher of the two -------- */
penalty(BagId,complimentary,Pen) :-
      bag(BagId,L,W,H,Weight),
      dims_sum(L,W,H,Sum),
      oversize_fee(Sum,OS),
      overweight_fee(Weight,70,OW),
      Pen is max(OS,OW).

penalty(BagId,charged,Pen) :-
      bag(BagId,L,W,H,Weight),
      dims_sum(L,W,H,Sum),
      oversize_fee(Sum,OS),
      overweight_fee(Weight,50,OW),
      Pen is max(OS,OW).

/* -------- base checked-bag fee for First Class, US<->Qatar -- */
bag_fee(1,0).
bag_fee(2,0).
bag_fee(3,0).
bag_fee(N,200) :- N>=4.

/* ==============  Helper predicates  ====================== */

/* choose 3 different elements (A<B<C) from a list */
choose_three(List,A,B,C) :-
      append(_,[A|T1],List),
      append(_,[B|T2],T1),
      member(C,T2).

/* put the 3 chosen freebies first, keep the rest orderless  */
ordered_list(A,B,C,Ordered) :-
      checked_bag_ids(All),
      select(A,All,R1),
      select(B,R1,R2),
      select(C,R2,R3),
      Ordered = [A,B,C|R3].

/* total for one particular choice of the 3 complimentary bags */
cost_for_choice(A,B,C,Total) :-
      ordered_list(A,B,C,Ordered),
      cost_bags(Ordered,1,BagsCost,Penalties),
      flight_cost(Tix),
      Total is Tix + BagsCost + Penalties.

/* walk through the ordered list, accumulating cost            */
cost_bags([],_,0,0).
cost_bags([Bag|Bs],Idx,CostSum,PenSum) :-
      (Idx =< 3 -> Kind = complimentary ; Kind = charged),
      bag_fee(Idx,BaseFee),
      penalty(Bag,Kind,Pen),
      Next is Idx+1,
      cost_bags(Bs,Next,RestCost,RestPen),
      CostSum is BaseFee + RestCost,
      PenSum  is Pen      + RestPen.

/* ==============  Global minimum =========================== */
total_cost(Min) :-
      checked_bag_ids(List),
      findall(T,
              ( choose_three(List,A,B,C),
                cost_for_choice(A,B,C,T) ),
              Totals),
      min_list(Totals,Min).

/* ----------------  Query & output  ------------------------ */
:- total_cost(Total), format('Total cost: ~w~n',[Total]).
:- halt.