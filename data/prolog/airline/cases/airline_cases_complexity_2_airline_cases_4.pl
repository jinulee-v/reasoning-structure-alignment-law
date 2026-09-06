:- use_module(library(lists)).

% ------------------------------------------------------------------
% Basic facts about the itinerary
% ------------------------------------------------------------------
ticket(63).                       % the airfare itself (USD)
cabin_class(business).            % Daniel is a Business Class customer
route(within_us).                 % Philadelphia - Las Vegas is wholly within the U.S.

% ------------------------------------------------------------------
% Checked-bag facts  (carry-on / personal item not listed - free)
% bag(ID, SizeInches, WeightLbs).
% SizeInches = L+W+H
% ------------------------------------------------------------------
bag(1,101,76).   % 50 x 27 x 24  - oversize & >70 lbs
bag(2,98,64).    % 45 x 32 x 21
bag(3,64,52).    % 36 x 16 x 12
bag(4,65,53).    % 35 x 20 x 10
bag(5,100,66).   % 49 x 30 x 21
bag(6,63,51).    % 37 x 15 x 11
bag(7,85,56).    % 44 x 22 x 19
bag(8,93,52).    % 44 x 29 x 20
bag(9,101,82).   % 49 x 31 x 21
bag(10,64,79).   % 35 x 16 x 13

% ------------------------------------------------------------------
% Positional order of the 10 checked pieces
% (first 2 free for Business Class, then 3rd, 4th...)
% ------------------------------------------------------------------
pos(1,1).  pos(2,2).  pos(3,3).  pos(4,4).  pos(5,5).
pos(6,6).  pos(7,7).  pos(8,8).  pos(9,9).  pos(10,10).

% ------------------------------------------------------------------
% Checked-bag fee (within U.S., Business Class)
% ------------------------------------------------------------------
bag_fee(Pos,0)   :- Pos =< 2.            % 1st and 2nd free
bag_fee(3,150).                         % 3rd bag
bag_fee(Pos,200) :- Pos >= 4.            % 4th bag and beyond

% ------------------------------------------------------------------
% Oversize fees - within U.S.
% ------------------------------------------------------------------
oversize_fee(Size,0)   :- Size =< 62.
oversize_fee(Size,30)  :- Size > 62,  Size =< 65.
oversize_fee(Size,200) :- Size > 65,  Size =< 115.

% ------------------------------------------------------------------
% Over-weight fees - within U.S.
% ------------------------------------------------------------------
overweight_fee(W,0)   :- W =< 50.
overweight_fee(W,30)  :- W > 50, W =< 53.
overweight_fee(W,100) :- W > 53, W =< 70.
overweight_fee(W,200) :- W > 70, W =< 100.

% ------------------------------------------------------------------
% For a bag that is both oversize *and* overweight,
% only the higher of the two extra fees applies.
% ------------------------------------------------------------------
extra_fee(Size,Weight,Fee) :-
    oversize_fee(Size,SF),
    overweight_fee(Weight,WF),
    (SF >= WF -> Fee = SF ; Fee = WF).

% ------------------------------------------------------------------
% Total fee for an individual bag
% ------------------------------------------------------------------
bag_total(ID,Pos,Total) :-
    bag(ID,Size,Weight),
    pos(ID,Pos),
    bag_fee(Pos,BF),
    extra_fee(Size,Weight,EF),
    Total is BF + EF.

% ------------------------------------------------------------------
% Sum of all checked-bag related charges
% ------------------------------------------------------------------
bags_fees_total(Total) :-
    findall(F,bag_total(_,_,F),Fs),
    sum_list(Fs,Total).

% ------------------------------------------------------------------
% Grand total owed by Daniel (ticket + all bag charges)
% ------------------------------------------------------------------
total_cost(Total) :-
    ticket(T),
    bags_fees_total(BF),
    Total is T + BF.

% ------------------------------------------------------------------
% Query: compute and display the answer
% ------------------------------------------------------------------
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.