/*---------------------------------------------------------------
   Robert - First Class   |  Rome (Italy / Europe)  ->  Seattle
-----------------------------------------------------------------
   Statutory background (extract)
     - First Class between Europe and U.S.:
         - 1st, 2nd, 3rd checked bags ............. $0 each
         - 4th bag and beyond ..................... $200 each
     - Size (L+W+H) > 62-65 in .................... $30
                 > 65-115 in ...................... $150
     - Weight limits
         Complimentary bag ........................ 70-lb threshold
         Charged bag ............................... 50-lb threshold
         > 50-53 lb ............................... $30
         > 53-70 lb ............................... $100
         > 70-100 lb .............................. $200
     - Penalty for a bag = higher of oversize vs. overweight
-----------------------------------------------------------------*/


/* ------------  Flight ticket  --------------------------------*/
flight_cost(536).


/* ------------  Bags to be checked (Id, L, W, H, Weight) ------*/
bag(2, 38,12,13,57).
bag(3, 33,19,12,56).
bag(4, 38,19,16,66).
bag(5, 37,18,10,64).
bag(6, 45,27,19,53).
bag(7, 36,15,14,53).
bag(8, 47,24,21,51).
bag(9, 41,22,14,55).
bag(10,33,18,12,51).
bag(11,36,18,11,64).

/* list of all checked-bag Ids (carry-on bag #1 is omitted) */
checked_bag_ids([2,3,4,5,6,7,8,9,10,11]).

/* ------------  Oversize fee between Europe <-> U.S. -------------*/
oversize_fee(Sum,Fee) :-
       (   Sum =< 62      -> Fee = 0
       ;   Sum =< 65      -> Fee = 30
       ;   Sum =< 115     -> Fee = 150 ).

/* ------------  Overweight fee  --------------------------------*/
/* 'Thresh' is 70 lb for complimentary bags, 50 lb for charged.  */
overweight_fee(W,Thresh,Fee) :-
       (   W =< Thresh        -> Fee = 0
       ;   W =< 53            -> Fee = 30
       ;   W =< 70            -> Fee = 100
       ;   W =< 100           -> Fee = 200 ).

/* ------------  Penalty (higher of oversize vs. overweight) ----*/
dims_sum(L,W,H,S) :- S is L+W+H.

penalty(BagId,comp,Pen) :-
       bag(BagId,L,W,H,Weight),
       dims_sum(L,W,H,Sum),
       oversize_fee(Sum,OS),
       overweight_fee(Weight,70,OW),          % complimentary bag
       Pen is max(OS,OW).

penalty(BagId,charged,Pen) :-
       bag(BagId,L,W,H,Weight),
       dims_sum(L,W,H,Sum),
       oversize_fee(Sum,OS),
       overweight_fee(Weight,50,OW),          % charged bag
       Pen is max(OS,OW).

/* ------------  Checked-bag base fee by ordinal position -------*/
bag_fee(Pos,0)   :- Pos =< 3.      % 1st-3rd bags free
bag_fee(Pos,200) :- Pos  > 3.      % 4th bag and beyond

/* ------------  Helper: choose any 3 different elements --------*/
choose_three(List,A,B,C) :-
       select(A,List,L1),
       select(B,L1,L2), A @< B,
       select(C,L2,_),  B @< C.

/* Put the 3 complimentary bags first in the ordered list         */
ordered_list(A,B,C,Ordered) :-
       checked_bag_ids(All),
       select(A,All,R1),
       select(B,R1,R2),
       select(C,R2,Rest),
       Ordered = [A,B,C|Rest].

/* ------------  Cost for a particular choice of 3 freebies -----*/
cost_for_choice(A,B,C,Total) :-
       ordered_list(A,B,C,Ordered),
       cost_bags(Ordered,1,BaseFees,Penalties),
       flight_cost(Tix),
       Total is Tix + BaseFees + Penalties.

/* Walk through ordered list accumulating fees and penalties      */
cost_bags([],_,0,0).
cost_bags([Bag|Bs],Idx,FeeSum,PenSum) :-
       (Idx =< 3 -> Type = comp ; Type = charged),
       bag_fee(Idx,Base),
       penalty(Bag,Type,Pen),
       NextIdx is Idx + 1,
       cost_bags(Bs,NextIdx,RestBase,RestPen),
       FeeSum is Base + RestBase,
       PenSum  is Pen  + RestPen.

/* ------------  Minimal total over all ways to pick freebies ---*/
compute_total(Min) :-
       checked_bag_ids(L),
       findall(T,
               ( choose_three(L,A,B,C),
                 cost_for_choice(A,B,C,T) ),
               Ts),
       min_list(Ts,Min).

/* ------------  Query & print result ---------------------------*/
:- compute_total(Cost), format('Total cost: ~w~n', [Cost]), halt.