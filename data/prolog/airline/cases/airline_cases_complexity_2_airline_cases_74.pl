/****************************************************************
 * Statutory rules (only the parts that apply to this itinerary) *
 ****************************************************************/

% route involved in this case
route(south_korea).        % Salt-Lake-City (U.S.)  ->  Seoul (South Korea)

% passenger's cabin class
cabin(basic_economy).

/* ---------------- Checked-bag 'base' fees (USD) --------------- */
% 1st / 2nd / 3rd / 4th-plus bag for Basic-Economy to / from
% India, China, Japan, South-Korea, Hong-Kong, Australia, N-Zealand
base_fee(1, basic_economy, south_korea,  75).
base_fee(2, basic_economy, south_korea, 100).
base_fee(3, basic_economy, south_korea, 200).
base_fee(N, basic_economy, south_korea, 200) :- N >= 4.

/* --------------- Overweight-only surcharges (USD) ------------- */
% weight in pounds
overweight_fee(W, _,            0)  :- W =< 50.          % within allowance
overweight_fee(W, _,           30)  :- W  > 50, W =< 53. % 50-53 lb
overweight_fee(W, south_korea,100)  :- W  > 53, W =< 70. % 53-70 lb
overweight_fee(W, south_korea,450)  :- W  > 70, W =<100. % 70-100 lb

/* ---------------- Oversize-only surcharges (USD) -------------- */
% linear size = L+W+H   (in inches)
oversize_fee(S, _,            0)  :- S =< 62.            % within allowance
oversize_fee(S, _,           30)  :- S  > 62, S =< 65.   % 62-65 in
oversize_fee(S, south_korea,200)  :- S  > 65, S =<115.   % 65-115 in

/* ----------- Combined "extra" fee for one checked bag -------- */
% The larger of the overweight / oversize fees applies
extra_fee(Size,Weight,Route,Fee) :-
    oversize_fee(Size,Route,OverSizeFee),
    overweight_fee(Weight,Route,OverWtFee),
    Fee is max(OverSizeFee,OverWtFee).

/****************************************************************
 * Facts that describe William's checked baggage                *
 ****************************************************************/

% bag(ID, L, W, H, Weight).     (dimensions in inches, weight in lb)
bag(1, 36,17,12, 51).
bag(2, 39,22,18, 87).
bag(3, 34,21, 9, 96).
bag(4, 36,15,14, 66).
bag(5, 38,22,15, 51).
bag(6, 48,30,24, 52).
bag(7, 35,17,12, 62).
bag(8, 38,15,10, 92).
bag(9, 48,32,27, 68).
bag(10,37,16,11, 90).

/****************************************************************
 * Compute cost for each checked bag                            *
 ****************************************************************/
bag_cost(ID, Cost) :-
    bag(ID,L,W,H,Weight),
    route(Route),
    cabin(Class),
    Size is L+W+H,
    extra_fee(Size,Weight,Route,Extra),
    base_fee(ID,Class,Route,Base),
    Cost is Base + Extra.

/****************************************************************
 * Total cost (bags + ticket)                                   *
 ****************************************************************/
total_bag_cost(Total) :-
    findall(C, bag_cost(_,C), Cs),
    sumlist(Cs, Total).

ticket_price(407).     % given in the case statement

total_cost(Total) :-
    total_bag_cost(Bags),
    ticket_price(Ticket),
    Total is Bags + Ticket.

/****************************************************************
 * Query                                                         *
 ****************************************************************/
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.