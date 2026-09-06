:- format("~w~n", ["Label: 2961"]).
/* =========================================================
   Jessica - Business Class        Charlotte  ->  Xiamen
   Statutory luggage cost program
   ========================================================= */

/* -------------  Flight information  --------------------- */

flight_cost(571).                       /* ticket price $ */

/* checked bags:  bag(Id,Length,Width,Height,Weight)        */
bag(2,49,28,22,52).
bag(3,35,17,13,86).
bag(4,33,22,10,62).
bag(5,41,21,18,52).
bag(6,45,29,20,95).
bag(7,36,15,13,53).
bag(8,36,17,11,52).

/* list of all checked-bag Ids (carry-on not listed)        */
checked_bag_ids([2,3,4,5,6,7,8]).

/* -------------  Statutory rules  ------------------------ */

/* total of the 3 dimensions */
dims_sum(L,W,H,S) :- S is L+W+H.

/*  Oversize fees : U.S. <-> China (same scale as "Asia" rows)
      - over 62"-65"  : $30
      - over 65"-115" : $200                                 */
oversize_fee(Sum,Fee) :-
          (   Sum =< 62      -> Fee = 0
          ;   Sum =< 65      -> Fee = 30
          ;   Sum =< 115     -> Fee = 200 ).

/*  Overweight fees : U.S. <-> China
      For CHARGED bags   -> 50-lb free limit
      For COMPLIMENTARY  -> 70-lb free limit                */
overweight_fee(W,FreeLimit,Fee) :-
          (   W =< FreeLimit -> Fee = 0               % within allowance
          ;   W =< 53        -> Fee = 30
          ;   W =< 70        -> Fee = 100
          ;   W =< 100       -> Fee = 450 ).

/* penalty = higher of oversize vs overweight               */
penalty(BagId,comp,Pen) :-
          bag(BagId,L,W,H,Weight),
          dims_sum(L,W,H,Sum),
          oversize_fee(Sum,OS),
          overweight_fee(Weight,70,OW),        % complimentary bag
          Pen is max(OS,OW).

penalty(BagId,charged,Pen) :-
          bag(BagId,L,W,H,Weight),
          dims_sum(L,W,H,Sum),
          oversize_fee(Sum,OS),
          overweight_fee(Weight,50,OW),        % charged bag
          Pen is max(OS,OW).

/* Checked-bag base fees for Business Class on this route   */
bag_fee(1,0).
bag_fee(2,0).
bag_fee(N,200) :- N >= 3.

/* -------------  Helper predicates  ---------------------- */

/* pick two different list elements (F1 < F2 in order)      */
choose_two(List,F1,F2) :-
          append(_,[F1|Tail],List),
          member(F2,Tail).

/* place the 2 freebies first, keep relative order for rest */
ordered_list(F1,F2,Ordered) :-
          checked_bag_ids(All),
          select(F1,All,R1),
          select(F2,R1,R2),
          Ordered = [F1,F2 | R2].

/* cost for a specific choice of the 2 complimentary bags   */
cost_for_choice(F1,F2,Total) :-
          ordered_list(F1,F2,OL),
          bag_costs(OL,1,BagsTotal),
          flight_cost(Flight),
          Total is Flight + BagsTotal.

/* walk through ordered list accumulating costs             */
bag_costs([],_,0).
bag_costs([Bag|Bs],Idx,Total) :-
          (Idx =< 2 -> Kind = comp ; Kind = charged),
          bag_fee(Idx,BFee),
          penalty(Bag,Kind,Pen),
          Next is Idx+1,
          bag_costs(Bs,Next,Rest),
          Total is BFee + Pen + Rest.

/* minimal total over every possible set of 2 free bags     */
total_cost(Min) :-
          checked_bag_ids(L),
          findall(T,
                  (choose_two(L,B1,B2), cost_for_choice(B1,B2,T)),
                  Totals),
          min_list(Totals,Min).

/* -------------  Produce the answer  --------------------- */
:- total_cost(Total), format('Total cost: ~w~n',[Total]).
:- halt.