/* ----------  Rules from the statutes that are relevant to this case ---------- */

/* route : U.S.  <->  Europe   (Salt Lake City - Zurich)                     */
/* travel class : Premium Economy                                            */

/* ------------------------ helper predicates ------------------------------ */
size_sum(L,W,H,S)        :- S is L+W+H.

/* oversize fees for the Europe <-> U.S. region                                */
oversize_fee(Size,0)     :- Size =< 62.
oversize_fee(Size,30)    :- Size  > 62, Size =< 65.
oversize_fee(Size,150)   :- Size  > 65, Size =< 115.

 /* overweight fees (all regions share the same numbers we need here)        */
overweight_fee(W,0)      :- W =< 50.
overweight_fee(W,30)     :- W  > 50, W =< 53.
overweight_fee(W,100)    :- W  > 53, W =< 70.

/* choose the higher of the two surcharges                                   */
max(A,B,A)               :- A >= B.
max(A,B,B)               :- B >  A.

/* base checked-bag fees for Premium Economy on Europe <-> U.S. routes         */
bag_base_fee(N,0)        :- N =< 2.          /* 1st & 2nd bags free          */
bag_base_fee(N,200)      :- N >= 3.          /* 3rd bag and on               */

/* ------------------------------ Facts ------------------------------------ */
ticket_price(251).

/* bag(Number, Length, Width, Height, Weight)  -  10 checked bags            */
bag(1,39,21,19,65).
bag(2,47,31,21,52).
bag(3,40,27,15,53).
bag(4,47,22,22,66).
bag(5,47,27,25,52).
bag(6,45,28,22,51).
bag(7,35,17,11,52).
bag(8,55,30,30,61).
bag(9,37,14,13,53).
bag(10,33,19,13,52).

/* ------------------- computing the charge for each bag ------------------- */
bag_total_charge(N,TotalFee) :-
    bag(N,L,W,H,Weight),
    size_sum(L,W,H,Size),
    oversize_fee(Size,OSFee),
    overweight_fee(Weight,OWFee),
    max(OSFee,OWFee,ExtraFee),          /* only the higher of the two        */
    bag_base_fee(N,BaseFee),
    TotalFee is BaseFee + ExtraFee.

/* ------------- aggregate all bag fees and the ticket price --------------- */
total_bag_fees(Total) :-
    findall(Fee, bag_total_charge(_,Fee), Fees),
    sumlist(Fees,Total).

total_cost(TotalCost) :-
    total_bag_fees(BagTotal),
    ticket_price(Ticket),
    TotalCost is BagTotal + Ticket.

/* --------------------------- final query --------------------------------- */
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.