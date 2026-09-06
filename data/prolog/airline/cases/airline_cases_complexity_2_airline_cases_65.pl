/* =========  Statutory rules that matter for this case  ========== */

/* --------------  Route and service class ------------------------ */
route(portland, jerusalem, us_israel).        /* Portland (U.S.) -> Jerusalem (Israel) */
service_class(premium_economy).

/* --------------  Ticket cost ------------------------------------ */
ticket_cost(863).

/* --------------  Bags (length, width, height, weight) ------------ */
bag(bag1 ,22,13, 9,  6).
bag(bag2 ,41,26,20, 70).
bag(bag3 ,38,24,18, 53).
bag(bag4 ,34,17,14, 51).
bag(bag5 ,37,18,10, 54).
bag(bag6 ,40,27,16, 51).
bag(bag7 ,37,14,12, 57).
bag(bag8 ,33,18,13, 53).
bag(bag9 ,33,19,12, 53).
bag(bag10,38,16,10, 60).
bag(bag11,36,20,15, 53).

/* =============================================================== */
/* ----------------  Carry-on allowance  -------------------------- */
carry_on_dimensions_max(22,14,9).

qualifies_carry_on(BagID) :-
    bag(BagID,L,W,H,_),
    carry_on_dimensions_max(MaxL,MaxW,MaxH),
    L =< MaxL, W =< MaxW, H =< MaxH.

/* Jessica is bringing one carry-on (bag1)                        */
carry_on(bag1).

/* Every other bag is checked, in the order given below            */
checked_bag_list([bag2,bag3,bag4,bag5,bag6,bag7,bag8,bag9,bag10,bag11]).

checked_bag(BagID,Index) :-
    checked_bag_list(List),
    nth1(Index,List,BagID).

/* ----------------  Base checked-bag fees  ----------------------- */
/* For the route U.S. <-> Israel and Premium Economy:                */
/*  - 1st and 2nd checked bags: free                                */
/*  - 3rd bag and beyond: $200 each                                 */
bag_base_fee(Index,0)  :- Index =< 2.          /* 1st & 2nd bag free */
bag_base_fee(Index,200):- Index  > 2.

/* ----------------  Oversize fees  ------------------------------- */
/* Linear size = L+W+H                                             */
bag_linear_size(B,Sum) :-
    bag(B,L,W,H,_),
    Sum is L+W+H.

/* For U.S. <-> Israel:                                              */
oversize_fee(Size,0 ) :- Size =< 62.
oversize_fee(Size,30) :- Size  > 62, Size =< 65.
oversize_fee(Size,150):- Size  > 65, Size =< 115.

/* ----------------  Overweight fees ------------------------------ */
overweight_fee(Weight,0 )  :- Weight =< 50.
overweight_fee(Weight,30)  :- Weight  > 50, Weight =< 53.
overweight_fee(Weight,100) :- Weight  > 53, Weight =< 70.

/* ----------------  Surcharge per bag ---------------------------- */
/* If both oversize & overweight apply, collect only the higher one */
bag_surcharge(BagID,Surcharge) :-
    bag(BagID,_,_,_,Weight),
    bag_linear_size(BagID,Size),
    oversize_fee(Size,OSFee),
    overweight_fee(Weight,OWFee),
    Surcharge is max(OSFee,OWFee).

/* ----------------  Total auxiliary sums ------------------------- */
total_base_bag_fees(Total) :-
    findall(Fee,
            (checked_bag(_,Index), bag_base_fee(Index,Fee)),
            Fees),
    sum_list(Fees,Total).

total_surcharges(Total) :-
    findall(Fee,
            (checked_bag(BagID,_), bag_surcharge(BagID,Fee)),
            Fees),
    sum_list(Fees,Total).

/* ----------------  Grand total ---------------------------------- */
total_cost(Total) :-
    ticket_cost(Ticket),
    total_base_bag_fees(BaseFees),
    total_surcharges(Surcharges),
    Total is Ticket + BaseFees + Surcharges.

/* ----------------  Query and output ----------------------------- */
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.