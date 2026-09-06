%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%  Statutory rules - (subset needed for this case only)
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

% ----------------  Carry-on allowance --------------------
carry_on_size_limit(22,14,9).           % inches (L,W,H)

% A bag is a carry-on if it does not exceed the carry-on limits
carry_on(BagID) :-
    bag(BagID,L,W,H,_),
    carry_on_size_limit(Lm,Wm,Hm),
    L =< Lm, W =< Wm, H =< Hm.

% ----------------  Base checked-bag fees -----------------
% For Premium-Economy on purely domestic U.S. itineraries
% BagNo = 1,2 : free
% BagNo = 3    : $150
% BagNo >=4    : $200
base_checked_fee(1,0).
base_checked_fee(2,0).
base_checked_fee(3,150).
base_checked_fee(N,200) :- N >= 4.

% ----------------  Oversize fees (domestic) --------------
oversize_fee(Size,Fee) :-
    Size > 62, Size =< 65,  Fee = 30.
oversize_fee(Size,Fee) :-
    Size > 65, Size =< 115, Fee = 200.
oversize_fee(Size,0) :-
    Size =< 62.

% ----------------  Over-weight fees (domestic) -----------
overweight_fee(W,Fee) :-
    W > 50,  W =< 53,  Fee = 30.
overweight_fee(W,Fee) :-
    W > 53,  W =< 70,  Fee = 100.
overweight_fee(W,Fee) :-
    W > 70,  W =< 100, Fee = 200.
overweight_fee(W,0) :-
    W =< 50.

% ----------------  Higher of over-size / over-weight -----
extra_fee(BagID,Fee) :-
    bag(BagID,L,W,H,Weight),
    Size is L+W+H,
    oversize_fee(Size,OSFee),
    overweight_fee(Weight,OWFee),
    Fee is max(OSFee,OWFee).

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%  Case facts - Michael's itinerary
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

ticket_price(182).

% bag(ID,Length,Width,Height,Weight).
bag(1,20,13,6,  9).
bag(2,35,19,11,66).
bag(3,35,16,12,75).
bag(4,38,15,12,56).
bag(5,45,31,20,51).
bag(6,50,33,31,51).
bag(7,40,23,16,98).
bag(8,35,17,11,77).

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%  Computations
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

% Produce list of checked bags (those that are NOT carry-ons)
checked_bag_list(List) :-
    findall(ID,(bag(ID,_,_,_,_), \+ carry_on(ID)),List).

% Annotate each checked bag with its sequence number (1-based)
checked_bag_with_index(IndexIDList) :-
    checked_bag_list(Bags),
    findall(N-ID,(nth1(N,Bags,ID)),IndexIDList).

% Cost of a single checked bag = base fee + max(over-size,over-weight)
checked_bag_cost(Seq-ID,Cost) :-
    base_checked_fee(Seq,Base),
    extra_fee(ID,Extra),
    Cost is Base + Extra.

% Sum of all checked-bag costs
total_checked_cost(Total) :-
    checked_bag_with_index(L),
    findall(Cost, (member(Pair,L), checked_bag_cost(Pair,Cost)), Costs),
    sum_list(Costs,Total).

% Grand total = ticket + checked-bag charges
total_cost(Total) :-
    ticket_price(T),
    total_checked_cost(CB),
    Total is T + CB.

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%  Produce answer
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
:- total_cost(Total), format('Total cost: ~w~n',[Total]).
:- halt.