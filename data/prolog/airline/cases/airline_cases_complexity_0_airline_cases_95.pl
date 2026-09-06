/* -------------  RULES (Statutes excerpt) ------------- */

/*  Base checked-bag fee for a Main Cabin customer on a wholly
    domestic (U.S. - U.S.) itinerary                       */
bag_base_fee(1,40).   /* 1st checked bag  */
bag_base_fee(2,45).   /* 2nd checked bag  */
bag_base_fee(3,150).  /* 3rd checked bag  */
bag_base_fee(N,200) :- N>=4.   /* 4th bag and beyond        */

/*  Oversize fee (domestic)                                 */
oversize_fee(DimSum,30)  :- DimSum > 62,  DimSum =< 65.
oversize_fee(DimSum,200) :- DimSum > 65,  DimSum =< 115.
oversize_fee(DimSum,0)   :- DimSum =< 62.      /* not oversize */

/*  Over-weight fee (domestic)                              */
overweight_fee(W,30)  :- W  > 50, W =< 53.   /* 50-53 lb  */
overweight_fee(W,100) :- W  > 53, W =< 70.   /* 53-70 lb  */
overweight_fee(W,0)   :- W =< 50.            /* not overweight */

/*  For bags that are both oversize and overweight,
    the higher of the 2 surcharges applies                 */
special_fee(DimSum,W,F) :-
    oversize_fee(DimSum,OF),
    overweight_fee(W,WF),
    (OF >= WF -> F = OF ; F = WF).

/* -------------  FACTS (Linda's situation) ------------- */

ticket_price(262).

/* item(ID, Length, Width, Height, Weight).  All sizes in inches,
   weight in pounds                                           */
item(1,18,11,9,  7).
item(2,48,33,24,53).
item(3,38,16,10,53).
item(4,51,29,23,51).
item(5,36,18,10,58).

/* carry-on definition (max 22*14*9 in.) */
carry_on(ID) :-
    item(ID,L,W,H,_),
    L =< 22, W =< 14, H =< 9.

/* Exactly 1 free carry-on permitted; choose the one that qualifies
   with the smallest ID (any qualifying bag would do for this case) */
chosen_carry_on(ID) :-
    setof(I,carry_on(I),[ID|_]).

/* Checked bags = all items except the chosen carry-on             */
checked_bag(ID) :-
    item(ID,_,_,_,_),
    chosen_carry_on(C),
    ID \= C.

/* Give each checked bag its sequence number (1st, 2nd ...)          */
checked_bag_index(ID,Idx) :-
    findall(I,checked_bag(I),List),
    nth1(Idx,List,ID).

/* Cost of an individual checked bag                               */
bag_cost(ID,Cost) :-
    checked_bag_index(ID,Idx),
    bag_base_fee(Idx,Base),
    item(ID,L,W,H,Weight),
    DimSum is L+W+H,
    special_fee(DimSum,Weight,Spec),
    Cost is Base + Spec.

/* Sum of all checked-bag costs                                    */
total_bag_fees(Total) :-
    findall(C,(bag_cost(_,C)),List),
    sum_list(List,Total).

/* Full trip cost (ticket + bags)                                  */
total_cost(Total) :-
    ticket_price(Tix),
    total_bag_fees(BagFees),
    Total is Tix + BagFees.

/* -------------  QUERY / OUTPUT ------------- */
:- total_cost(Total), format('Total cost: ~w~n',[Total]).
:- halt.