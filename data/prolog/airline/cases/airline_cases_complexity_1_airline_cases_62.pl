/* ===================================================================== */
/*  Statutory reasoning - Charles (Business Class, Dallas -> Ottawa)      */
/* ===================================================================== */

/* --------------  Carry-on limits ------------------------------------- */
carry_on_max(22,14,9).

/* bag(Id,Length,Width,Height,Weight) - ALL the customer's items         */
bag(1,22,13, 6,  6).     /* qualifies as the single carry-on            */
bag(2,41,17,14, 60).
bag(3,37,18,16, 65).
bag(4,38,15,12, 54).
bag(5,33,21, 9, 53).
bag(6,38,13,12, 96).
bag(7,33,20,12, 64).
bag(8,37,15,13, 52).

/* list of those items that will (must) be checked                       */
checked_bag_ids(Checked) :-
       findall(Id,
               ( bag(Id,_,_,_,_),
                 \+ carry_on(Id) ),
               Checked).

/* does an item qualify as the lone carry-on?                            */
carry_on(Id) :-
       bag(Id,L,W,H,_),
       carry_on_max(MaxL,MaxW,MaxH),
       L=<MaxL, W=<MaxW, H=<MaxH.

/* --------------  Checked-bag fees for Business on this route --------- */
/* Between / within U.S. and Canada                                      */
bag_fee(1,0).                 /* 1st checked bag - complimentary        */
bag_fee(2,0).                 /* 2nd checked bag - complimentary        */
bag_fee(3,150).               /* 3rd bag                                */
bag_fee(N,200) :- N>=4.       /* 4th and beyond                         */

/* --------------  Oversize fees (U.S. / Canada) ----------------------- */
oversize_fee(Dim,0)   :- Dim =< 62.
oversize_fee(Dim,30)  :- Dim > 62, Dim =< 65.
oversize_fee(Dim,200) :- Dim > 65, Dim =< 115.

/* --------------  Over-weight fees (U.S. / Canada) -------------------- */
/* Thresh is 70 lbs for complimentary bags, 50 lbs for charged bags      */
overweight_fee(W,Thresh,0)   :- W =< Thresh.
overweight_fee(W,_,30)       :- W  =< 53.
overweight_fee(W,_,100)      :- W > 53,  W =< 70.
overweight_fee(W,_,200)      :- W > 70,  W =< 100.

/* --------------  Penalty: higher of oversize vs overweight ----------- */
penalty(Id,comp,Pen) :-
       bag(Id,L,W,H,Weight),
       DimSum is L+W+H,
       oversize_fee(DimSum,OS),
       overweight_fee(Weight,70,OW),        % complimentary => 70-lb limit
       Pen is max(OS,OW).

penalty(Id,charged,Pen) :-
       bag(Id,L,W,H,Weight),
       DimSum is L+W+H,
       oversize_fee(DimSum,OS),
       overweight_fee(Weight,50,OW),        % charged bag   => 50-lb limit
       Pen is max(OS,OW).

/* --------------  Helper predicates ----------------------------------- */

/* pick 2 different freebies (F1<F2) from the checked list               */
choose_two(List,F1,F2) :-
       append(_,[F1|Tail],List),
       member(F2,Tail).

/* move the 2 chosen freebies to the front, keep original order for rest */
ordered_list(F1,F2,Ordered) :-
       checked_bag_ids(All),
       select(F1,All,Rest1),
       select(F2,Rest1,Rest),
       Ordered = [F1,F2|Rest].

/* compute cost for a specific choice of two complimentary bags          */
cost_for_choice(F1,F2,Total) :-
       ordered_list(F1,F2,Ordered),
       cost_bags(Ordered,1,BagFees,Penalties),
       flight_cost(Flight),
       Total is Flight + BagFees + Penalties.

/* walk through the ordered list accumulating fees and penalties         */
cost_bags([],_,0,0).
cost_bags([Bag|Bs],Idx,CostSum,PenSum) :-
       (Idx =< 2 -> Type = comp ; Type = charged),
       bag_fee(Idx,BFee),
       penalty(Bag,Type,Pen),
       NextIdx is Idx+1,
       cost_bags(Bs,NextIdx,RestCost,RestPen),
       CostSum is BFee + RestCost,
       PenSum  is Pen   + RestPen.

/* minimal total cost over all possible choices of 2 freebies            */
compute_total(MinTotal) :-
       checked_bag_ids(L),
       findall(T,
               ( choose_two(L,F1,F2),
                 cost_for_choice(F1,F2,T) ),
               Totals),
       min_list(Totals,MinTotal).

/* --------------  Flight ticket --------------------------------------- */
flight_cost(200).

/* ===================================================================== */
/*  Query: output the total amount due                                   */
:- compute_total(Cost), format('Total cost: ~w~n', [Cost]), halt.