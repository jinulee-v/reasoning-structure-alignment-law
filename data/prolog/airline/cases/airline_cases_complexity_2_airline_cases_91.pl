% ---------- Facts describing Thomas' trip ----------
% flight information
flight_region(us_europe).                 % Miami (U.S.)  -> Stockholm (Europe)
cabin_class(basic_economy).
ticket_price(341).

% every bag is written as  bag(Id, Length, Width, Height, Weight).
bag(1,21,14,7,  7).
bag(2,44,24,19,51).
bag(3,51,29,26,53).
bag(4,35,21,9, 51).
bag(5,38,21,15,51).
bag(6,37,14,13,53).
bag(7,50,28,27,53).
bag(8,52,26,27,62).
bag(9,50,24,25,65).
bag(10,37,17,9,70).
bag(11,47,28,22,56).

% first bag is used as the free carry-on
carry_on_id(1).

% ---------- Size / weight helpers ----------
size(BagId, Size) :- bag(BagId,L,W,H,_), Size is L+W+H.
weight(BagId, W)  :- bag(BagId,_,_,_,W).

% ---------- Base checked-bag fee (U.S. <-> Europe, Basic Economy) ----------
base_fee(1,75).
base_fee(2,100).
base_fee(N,200) :- N>=3.

% ---------- Oversize fee rules (U.S. <-> Europe) ----------
oversize_fee(BagId,30)  :- size(BagId,S), S>62, S=<65.
oversize_fee(BagId,150) :- size(BagId,S), S>65, S=<115.
oversize_fee(BagId,0)   :- size(BagId,S), S=<62.

% ---------- Overweight fee rules ----------
% over 50 - 53 lbs
overweight_fee(BagId,30)  :- weight(BagId,W), W>50, W=<53.
% over 53 - 70 lbs
overweight_fee(BagId,100) :- weight(BagId,W), W>53, W=<70.
% =< 50 lbs
overweight_fee(BagId,0)   :- weight(BagId,W), W=<50.

% ---------- Surcharge for a bag ----------
surcharge(BagId,Fee) :-
    oversize_fee(BagId,OverSize),
    overweight_fee(BagId,OverWt),
    (OverSize>=OverWt -> Fee=OverSize ; Fee=OverWt).

% ---------- Checked bag list (everything that is not carry-on) ----------
checked_bag_ids(Checked) :-
    findall(Id,(bag(Id,_,_,_,_), \+ carry_on_id(Id)), Checked).

% ---------- Fee for one checked bag (base + surcharge) ----------
checked_bag_fee(Index,BagId,TotalFee) :-
    base_fee(Index,Base),
    surcharge(BagId,Extra),
    TotalFee is Base+Extra.

% ---------- Total of all checked bags ----------
total_checked_bag_fees(Sum) :-
    checked_bag_ids(Ids),
    findall(Fee,
        (nth1(Index,Ids,Bid), checked_bag_fee(Index,Bid,Fee)),
        Fees),
    sum_list(Fees,Sum).

% ---------- Grand total ----------
total_cost(Total) :-
    total_checked_bag_fees(BagFees),
    ticket_price(Ticket),
    Total is Ticket + BagFees.

% ---------- Produce answer ----------
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.