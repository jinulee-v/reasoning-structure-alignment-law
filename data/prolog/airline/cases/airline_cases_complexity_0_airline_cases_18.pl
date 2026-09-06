% -------------------------------
%  Statutory rules  (abridged)
% -------------------------------
:- use_module(library(lists)).

% carry-on / personal-item limits
carry_on_limits(22,14,9).          % L, W, H  (inches)
personal_limits(18,14,8).

dims_fit(L,W,H,MaxL,MaxW,MaxH) :- L=<MaxL, W=<MaxW, H=<MaxH.

% checked-bag base fees (Basic-Economy, wholly within U.S.)
bag_base_fee(1,40).
bag_base_fee(2,45).
bag_base_fee(3,150).
bag_base_fee(4,200).
bag_base_fee(N,200) :- N>=5.

% overweight fees (within U.S.)
overweight_fee(W,0)   :- W=<50.
overweight_fee(W,30)  :- W>50, W=<53.
overweight_fee(W,100) :- W>53, W=<70.
overweight_fee(W,200) :- W>70, W=<100.

% oversize fees (within U.S.)
oversize_fee(L,W,H,Fee) :-
    S is L+W+H,
    (   S =< 62            -> Fee = 0
    ;   S =< 65            -> Fee = 30
    ;   S =< 115           -> Fee = 200
    ).

% -------------------------------------------------
%  Case facts - Robert (Basic-Economy LAS->CLT)
% -------------------------------------------------
item(item1,22,12, 8, 12).   % backpack (carry-on size)
item(item2,33,18,12, 57).   % luggage box
item(item3,35,19,10, 99).   % luggage box
item(item4,33,22,10, 82).   % luggage box
item(item5,38,15,10, 56).   % backpack (too large for carry-on)

item_order([item1,item2,item3,item4,item5]).  % order presented at airport

% -------------------------------------------------
%  Derived facts
% -------------------------------------------------
eligible_carry(ID) :-
    item(ID,L,W,H,_),
    carry_on_limits(MaxL,MaxW,MaxH),
    dims_fit(L,W,H,MaxL,MaxW,MaxH).

% first eligible item in presentation order is taken as the free carry-on
carry_on_selected(ID) :-
    item_order(List),
    member(ID,List),
    eligible_carry(ID),
    !.

checked_items(Checked) :-
    item_order(List),
    (   carry_on_selected(Carry)
    ->  exclude(=(Carry),List,Checked)
    ;   Checked = List).

additional_fee(BagID,Add) :-
    item(BagID,L,W,H,Wt),
    oversize_fee(L,W,H,OS),
    overweight_fee(Wt,OW),
    max_list([OS,OW],Add).   % only the higher of over-size / over-weight

bag_fee(BagID,Idx,Fee) :-
    bag_base_fee(Idx,Base),
    additional_fee(BagID,Add),
    Fee is Base + Add.

total_bag_fees(Total) :-
    checked_items(List),
    findall(F,(nth1(I,List,B),bag_fee(B,I,F)),Fees),
    sumlist(Fees,Total).

flight_ticket_cost(286).

total_cost(Total) :-
    total_bag_fees(Bags),
    flight_ticket_cost(Ticket),
    Total is Bags + Ticket.

% -------------------------------------------------
%  Query
% -------------------------------------------------
:- total_cost(Total), format('Total cost: ~w~n',[Total]).
:- halt.