%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%  Statutory rules (only the parts that matter for
%  the present case: Main-Cabin passenger,
%  U.S. <-> Europe route, checked-bag order 1...7,
%  oversize / overweight tables for that route).
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

% -------------------------
%  Carry-on qualification
% -------------------------
carry_on_dimensions(22,14,9).   % max L,W,H for a carry-on

is_carry_on(L,W,H) :-
    carry_on_dimensions(MaxL,MaxW,MaxH),
    L =< MaxL, W =< MaxW, H =< MaxH.

% -------------------------
%  Base checked-bag fees
% -------------------------
base_checked_fee(1,0).                 % 1st bag is free (Trans-Atlantic, Main Cabin)
base_checked_fee(2,100).               % 2nd bag
base_checked_fee(N,200) :- N >= 3.     % 3rd and every other bag

% -------------------------
%  Oversize fees (U.S. <-> Europe)
% -------------------------
oversize_fee(DimSum,Fee) :-
    DimSum =< 62,                     Fee = 0 ;                        % not oversize
    DimSum  > 62, DimSum =< 65,       Fee = 30 ;
    DimSum  > 65, DimSum =< 115,      Fee = 150 .

% -------------------------
%  Over-weight fees (U.S. <-> Europe)
% -------------------------
overweight_fee(Wt,Fee) :-
    Wt =< 50,                         Fee = 0 ;                        % within allowance
    Wt  > 50, Wt =< 53,               Fee = 30 ;
    Wt  > 53, Wt =< 70,               Fee = 100.

% -------------------------
%  Highest of over-size / over-weight
% -------------------------
special_fee(BagId,Fee) :-
    bag(BagId,L,W,H,Weight),
    DimSum is L+W+H,
    oversize_fee(DimSum,OverSize),
    overweight_fee(Weight,OverWeight),
    Fee is max(OverSize,OverWeight).

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%  Facts for Jennifer's case
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

% bag(Id, Length, Width, Height, Weight)

bag(1,22,14,6,  8).    % carry-on (will not be checked)
bag(2,48,32,26,52).
bag(3,44,26,22,66).
bag(4,36,16,11,52).
bag(5,48,33,25,69).
bag(6,50,32,25,68).
bag(7,53,34,27,54).
bag(8,35,17,12,52).

% Flight ticket price
ticket_price(344).

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%  Deriving which bags are checked
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

checked_bag(BagId) :-
    bag(BagId,L,W,H,_),
    \+ is_carry_on(L,W,H).     % every bag that is NOT carry-on

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%  Fee for a particular checked bag in positional order
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

bag_cost(BagId,Pos,TotalFee) :-
    base_checked_fee(Pos,Base),
    special_fee(BagId,Special),
    TotalFee is Base + Special.

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%  Assemble all checked-bag fees
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

all_checked_bag_ids(CheckedIds) :-
    findall(Id, checked_bag(Id), CheckedIds).

checked_bag_fees(Sum) :-
    all_checked_bag_ids(Ids),
    checked_bag_fees(Ids,1,Sum).

checked_bag_fees([],_,0).
checked_bag_fees([Id|Rest],Pos,Sum) :-
    bag_cost(Id,Pos,Fee),
    NextPos is Pos+1,
    checked_bag_fees(Rest,NextPos,RestSum),
    Sum is Fee + RestSum.

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%  Grand total
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

total_cost(Total) :-
    ticket_price(Ticket),
    checked_bag_fees(BagFees),
    Total is Ticket + BagFees.

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%  Query requested by the grading harness
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.