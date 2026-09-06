:- format("~w~n", ["Label: 2564"]).
/* ============================================================= */
/*  Elizabeth - First Class - New Orleans (MSY) -> Orlando (MCO)  */
/*  Route: Domestic (within the U.S.)                            */
/*  Statutory baggage rules applied exactly as in the examples   */
/* ============================================================= */


/* ----------  Cost of the ticket  ----------------------------- */
flight_cost(214).


/* ----------  Baggage list (carry-on already excluded) -------- */
/* bag(Id, Length, Width, Height, Weight)                       */
bag(2,36,14,14,98).          /* luggage / backpack  #2 */
bag(3,37,17,10,73).          /* luggage / backpack  #3 */
bag(4,52,32,27,65).          /* luggage / backpack  #4 */
bag(5,35,17,13,83).          /* luggage / backpack  #5 */
bag(6,34,15,14,87).          /* luggage / box       #6 */
bag(7,39,24,20,69).          /* luggage / backpack  #7 */
bag(8,43,23,16,83).          /* luggage / box       #8 */

/* ordered list of all checked-bag Ids (carry-on '1' omitted) */
checked_bag_ids([2,3,4,5,6,7,8]).



/* ============================================================= */
/*  Statutory rules - Domestic (U.S. / Canada / PR / USVI)       */
/* ============================================================= */

/* ----------  Dimension helpers  ------------------------------ */
dims_sum(L,W,H,S) :- S is L+W+H.

/* ----------  Over-SIZE fees (in inches) ---------------------- */
oversize_fee(Sum,Fee) :-
       (   Sum =< 62        -> Fee = 0
       ;   Sum =< 65        -> Fee = 30
       ;   Sum =< 115       -> Fee = 200).

/* ----------  Over-WEIGHT fees (in pounds) -------------------- */
/* 'Thresh' is 70 lb for complimentary bags, 50 lb for charged   */
overweight_fee(W,Thresh,Fee) :-
       (   W =< Thresh      -> Fee = 0
       ;   W =< 53          -> Fee = 30
       ;   W =< 70          -> Fee = 100
       ;   W =< 100         -> Fee = 200).

/* ----------  Penalty = higher of oversize vs overweight ------ */
penalty(Id,comp,Pen) :-
       bag(Id,L,W,H,Weight),
       dims_sum(L,W,H,Sum),
       oversize_fee(Sum,OS),
       overweight_fee(Weight,70,OW),     % complimentary => 70-lb limit
       Pen is max(OS,OW).

penalty(Id,charged,Pen) :-
       bag(Id,L,W,H,Weight),
       dims_sum(L,W,H,Sum),
       oversize_fee(Sum,OS),
       overweight_fee(Weight,50,OW),     % charged bag => 50-lb limit
       Pen is max(OS,OW).

/* ----------  Checked-bag BASE fees - First Class ------------- */
/* Domestic First: 1st & 2nd bag free; 3rd: $150; 4th+: $200     */
bag_fee(1,0).
bag_fee(2,0).
bag_fee(3,150).
bag_fee(N,200) :- N >= 4.



/* ============================================================= */
/*           Helper predicates to explore fee options            */
/* ============================================================= */

/* choose any two different elements F1<F2 from a list */
choose_two(List,F1,F2) :-
       append(_,[F1|Tail],List),
       member(F2,Tail).

/* place the two freebies at positions 1 & 2, keep order of rest */
ordered_list(F1,F2,Ordered) :-
       checked_bag_ids(All),
       select(F1,All,Rest1),
       select(F2,Rest1,Rest),
       Ordered = [F1,F2|Rest].

/* cost for a given choice of the 2 complimentary bags */
cost_for_choice(F1,F2,Total) :-
       ordered_list(F1,F2,Ordered),
       cost_bags(Ordered,1,BaseFees,Penalties),
       flight_cost(Tix),
       Total is Tix + BaseFees + Penalties.

/* walk over list accumulating BASE fees and PENALTIES            */
cost_bags([],_,0,0).
cost_bags([Bag|Bs],Idx,BaseSum,PenSum) :-
       (Idx =< 2 -> Kind = comp ; Kind = charged),
       bag_fee(Idx,BaseFee),
       penalty(Bag,Kind,Pen),
       Next is Idx+1,
       cost_bags(Bs,Next,BRest,PRest),
       BaseSum is BaseFee + BRest,
       PenSum  is Pen + PRest.

/* ----------  Grand-total: least cost over all free-bag choices */
total_cost(MinTotal) :-
       checked_bag_ids(L),
       findall(Cost,
               ( choose_two(L,F1,F2),
                 cost_for_choice(F1,F2,Cost)),
               Costs),
       min_list(Costs,MinTotal).



/* ============================================================= */
/*  Produce the answer exactly as required                       */
/* ============================================================= */
:- total_cost(Total), format('Total cost: ~w~n',[Total]).
:- halt.