/* -------------  Statutory rules (simplified to what we need) ------------- */

/* carry-on / personal-item limits */
personal_item_dims(18,14,8).
carry_on_dims(22,14,9).

/* premium-economy free checked-bag allowances (domestic) */
free_checked_bags(2).

/* Checked-bag base fees for a domestic Premium-Economy customer       */
/* (index = the chronological number of the checked bag)               */
checked_bag_base_fee(Index,0)  :- Index =< 2.     /* 1st & 2nd are free  */
checked_bag_base_fee(3,150).
checked_bag_base_fee(Index,200):- Index >= 4.

/* -------- overweight fees (domestic, in U.S. dollars) --------------- */
overweight_fee(W,0)   :- W =< 50.
overweight_fee(W,30)  :- W > 50 , W =< 53.
overweight_fee(W,100) :- W > 53 , W =< 70.
overweight_fee(W,200) :- W > 70 , W =< 100.

/* -------- oversize fees (domestic, in U.S. dollars) ----------------- */
oversize_fee(S,0)   :- S =< 62.
oversize_fee(S,30)  :- S > 62 , S =< 65.
oversize_fee(S,200) :- S > 65 , S =< 115.

/* ------------- helper: select the higher of two fees ---------------- */
higher_fee(A,B,A) :- A>=B, !.
higher_fee(_,B,B).

/* ---------------------- CASE FACTS ---------------------------------- */

ticket_price(50).          /* Joseph's airfare */

/* bag(Id, Length, Width, Height, Weight in lbs) */
bag(1,19,13,9, 11).
bag(2,41,30,17,91).
bag(3,38,15,11,52).
bag(4,43,24,18,92).
bag(5,38,23,19,98).
bag(6,42,16,17,52).
bag(7,34,17,13,52).
bag(8,37,14,14,60).

/* ---------- derive whether a bag is carry-on or needs to be checked -- */
carry_on(BagId) :-
    bag(BagId,L,W,H,_),
    carry_on_dims(MaxL,MaxW,MaxH),
    L =< MaxL, W =< MaxW, H =< MaxH.

checked_bag(BagId) :-
    bag(BagId,_,_,_,_),
    \+ carry_on(BagId).

/* ---------------- fee for ONE checked bag --------------------------- */
one_checked_bag_fee(BagId,Index,TotalFee) :-
    bag(BagId,L,W,H,Wt),
    DimSum is L+W+H,

    /* base checked-bag fee by index */
    checked_bag_base_fee(Index,BaseFee),

    /* overweight & oversize part (take the higher one) */
    overweight_fee(Wt,OWtFee),
    oversize_fee(DimSum,OSizeFee),
    higher_fee(OWtFee,OSizeFee,ExtraFee),

    TotalFee is BaseFee + ExtraFee.

/* ------------- accumulate fees for all checked bags ----------------- */
all_checked_bags_fee(Total) :-
    /* collect checked bags preserving a deterministic order */
    findall(Id, checked_bag(Id), BagList),
    all_checked_bags_fee(BagList,1,0,Total).

all_checked_bags_fee([],_,Acc,Acc).
all_checked_bags_fee([Bag|Rest],Index,Acc,Total) :-
    one_checked_bag_fee(Bag,Index,F),
    Acc1 is Acc + F,
    Index1 is Index + 1,
    all_checked_bags_fee(Rest,Index1,Acc1,Total).

/* ---------------------- TOTAL COST ---------------------------------- */
total_cost(Total) :-
    ticket_price(Tix),
    all_checked_bags_fee(BagFees),
    Total is Tix + BagFees.

/* ---------------------- QUERY --------------------------------------- */
:- total_cost(Total), format('Total cost: ~w~n',[Total]).
:- halt.